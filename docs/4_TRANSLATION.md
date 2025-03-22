# AWS Translate Guide

This guide provides step-by-step instructions for translating transcription files from AWS Transcribe to Polish while preserving timestamp information.

## Prerequisites

Before starting the translation process, ensure you have:

1. Properly configured AWS CLI with appropriate credentials
2. AWS Transcribe JSON output from a completed transcription job
3. Necessary permissions to access AWS Translate service

## Understanding AWS Transcribe Output Structure

The AWS Transcribe JSON output has the following key components:

1. Full text transcripts (without timestamps):
   ```json
   "transcripts": [
     {
       "transcript": "The complete transcript text..."
     }
   ]
   ```

2. Individual items with timestamps (words, punctuation):
   ```json
   "items": [
     {
       "start_time": "0.24",
       "end_time": "0.68",
       "alternatives": [
         {
           "confidence": "0.9987",
           "content": "Hello"
         }
       ],
       "type": "pronunciation"
     },
     {
       "alternatives": [
         {
           "content": ","
         }
       ],
       "type": "punctuation"
     }
   ]
   ```

3. Speaker labels (if enabled):
   ```json
   "speaker_labels": {
     "speakers": 2,
     "segments": [
       {
         "start_time": "0.24",
         "end_time": "5.04",
         "speaker_label": "spk_0",
         "items": [...]
       }
     ]
   }
   ```

## Basic Translation Approaches

### 1. Translate Complete Transcript

This approach translates the complete transcript without timestamps. Useful for getting a quick translation but doesn't preserve timestamps.

```bash
# Extract the transcript text
jq -r '.results.transcripts[0].transcript' Lex_Fridman-Narendra_Modi_transcript.json > original_transcript.txt

# Translate the complete text
aws translate translate-text \
    --text "$(cat original_transcript.txt)" \
    --source-language-code en \
    --target-language-code pl \
    --output json > full_translation.json

# Extract just the translated text
jq -r '.TranslatedText' full_translation.json > translated_transcript.txt
```

### 2. Advanced: Translate with Preserved Timestamps

This approach preserves timestamps by translating each segment or word individually.

## Creating a Script to Translate While Preserving Timestamps

Create a file named `translate_transcript.py`:

```bash
# Create the script file
cat > translate_transcript.py << 'EOF'
#!/usr/bin/env python3
import json
import boto3
import time
import sys
import os
import re
from concurrent.futures import ThreadPoolExecutor

def chunk_text(text, max_chunk_size=9000):
    """Break text into chunks of max_chunk_size bytes"""
    if not text or len(text.encode('utf-8')) <= max_chunk_size:
        return [text]
    
    # First try splitting by paragraphs
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        # If a single paragraph is too large, we'll need to split it by sentences
        if len(para.encode('utf-8')) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # Split paragraph by sentences (simple approach)
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sentence in sentences:
                # If a single sentence is too large (rare), split by character count
                if len(sentence.encode('utf-8')) > max_chunk_size:
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = ""
                    
                    # Split the sentence into chunks by byte size
                    while sentence:
                        # Find safe cutting point that doesn't exceed byte limit
                        # and doesn't cut words in the middle
                        i = 0
                        while i < len(sentence) and len(sentence[:i].encode('utf-8')) < max_chunk_size:
                            i += 1
                        
                        # Back up to the last word boundary if possible
                        cut_point = sentence.rfind(' ', 0, i)
                        if cut_point == -1 or cut_point == 0:
                            cut_point = max(i - 1, 1)
                        
                        chunks.append(sentence[:cut_point])
                        sentence = sentence[cut_point:].lstrip()
                else:
                    if len((current_chunk + " " + sentence).encode('utf-8')) <= max_chunk_size:
                        current_chunk = (current_chunk + " " + sentence).strip()
                    else:
                        chunks.append(current_chunk)
                        current_chunk = sentence
        else:
            # Check if adding this paragraph would exceed the limit
            if len((current_chunk + "\n" + para).encode('utf-8')) <= max_chunk_size:
                current_chunk = (current_chunk + "\n" + para).strip()
            else:
                chunks.append(current_chunk)
                current_chunk = para
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def translate_large_text(text, source_lang='en', target_lang='pl'):
    """Handle translation of text that may exceed AWS Translate's size limit"""
    translate = boto3.client('translate')
    
    if not text:
        return ""
    
    # Check if text exceeds limit
    if len(text.encode('utf-8')) <= 9000:
        try:
            response = translate.translate_text(
                Text=text,
                SourceLanguageCode=source_lang,
                TargetLanguageCode=target_lang
            )
            return response['TranslatedText']
        except Exception as e:
            print(f"Translation error: {e}")
            return f"[ERROR: {str(e)}]"
    
    # Break text into chunks
    chunks = chunk_text(text)
    translated_chunks = []
    
    # Translate each chunk
    for chunk in chunks:
        try:
            response = translate.translate_text(
                Text=chunk,
                SourceLanguageCode=source_lang,
                TargetLanguageCode=target_lang
            )
            translated_chunks.append(response['TranslatedText'])
            # Small delay to avoid hitting rate limits
            time.sleep(0.1)
        except Exception as e:
            print(f"Chunk translation error: {e}")
            translated_chunks.append(f"[ERROR: {str(e)}]")
    
    # Combine translated chunks
    return " ".join(translated_chunks)

def get_batch_translate(texts, source_lang='en', target_lang='pl'):
    """Batch translate texts using AWS Translate"""
    translate = boto3.client('translate')
    results = []
    
    # Process in batches of 10 to avoid throttling
    batch_size = 10
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_results = []
        
        # Submit all translations in parallel
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = []
            for text in batch:
                if not text.strip():  # Skip empty text
                    batch_results.append("")
                    continue
                
                # Use the new translate_large_text function instead of direct API call
                future = executor.submit(
                    translate_large_text,
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
                futures.append(future)
            
            # Collect results as they complete
            for future in futures:
                try:
                    result = future.result()
                    batch_results.append(result)
                except Exception as e:
                    print(f"Error in translation batch: {e}")
                    batch_results.append("[ERROR]")
        
        results.extend(batch_results)
        # Avoid rate limiting
        time.sleep(0.5)
    
    return results

def process_transcript(transcript_file, output_file):
    """Process a transcript file, translating while preserving timestamps"""
    print(f"Processing {transcript_file}...")
    
    # Load the transcript JSON
    with open(transcript_file, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)
    
    # Create a copy for modification
    translated_data = transcript_data.copy()
    
    # 1. Translate the full transcript in smaller chunks if necessary
    print("Translating full transcript text...")
    transcripts = transcript_data['results']['transcripts']
    
    # Handle each transcript segment
    for i, transcript_obj in enumerate(transcripts):
        transcript_text = transcript_obj['transcript']
        print(f"Translating transcript segment {i+1}/{len(transcripts)} ({len(transcript_text.encode('utf-8'))} bytes)")
        
        if len(transcript_text.encode('utf-8')) > 10000:
            print(f"Large transcript detected ({len(transcript_text.encode('utf-8'))} bytes). Breaking into chunks...")
            
            # Split transcript into paragraphs or logical segments
            segments = re.split(r'(?<=\.)\s+', transcript_text)
            translated_segments = []
            
            print(f"Processing {len(segments)} segments...")
            for j, segment in enumerate(segments):
                if j % 20 == 0:
                    print(f"Progress: {j}/{len(segments)} segments")
                
                if segment.strip():
                    translated = translate_large_text(segment, 'en', 'pl')
                    translated_segments.append(translated)
                    # Small delay to avoid rate limiting
                    time.sleep(0.2)
            
            # Reassemble the full translated text
            full_translated_text = ' '.join(translated_segments)
            translated_data['results']['transcripts'][i]['transcript'] = full_translated_text
        else:
            # Small enough to translate directly
            translated_text = translate_large_text(transcript_text, 'en', 'pl')
            translated_data['results']['transcripts'][i]['transcript'] = translated_text
    
    # 2. Translate individual items (words, etc.) for timestamps
    print("Translating individual words with timestamps...")
    items = transcript_data['results']['items']
    
    # Collect all word contents that need translation
    word_indices = []
    word_contents = []
    batch_size = 50  # Process in smaller batches
    
    for i, item in enumerate(items):
        # Only translate pronunciation items (actual words), not punctuation
        if item['type'] == 'pronunciation':
            alternatives = item['alternatives']
            for alt_idx, alt in enumerate(alternatives):
                word_indices.append((i, alt_idx))
                word_contents.append(alt['content'])
    
    # Process word batches
    print(f"Translating {len(word_contents)} individual words in batches of {batch_size}...")
    processed_words = 0
    
    for i in range(0, len(word_contents), batch_size):
        batch = word_contents[i:i+batch_size]
        batch_indices = word_indices[i:i+batch_size]
        
        # Batch translate words
        translated_batch = get_batch_translate(batch)
        
        # Replace word contents with translations
        for (item_idx, alt_idx), translated_word in zip(batch_indices, translated_batch):
            translated_data['results']['items'][item_idx]['alternatives'][alt_idx]['content'] = translated_word
        
        processed_words += len(batch)
        if processed_words % 200 == 0 or processed_words == len(word_contents):
            print(f"Progress: {processed_words}/{len(word_contents)} words translated")
        
        # Add a small delay between batches
        time.sleep(0.5)
    
    # 3. Add original_content field to keep both languages
    print("Adding original content references...")
    for i, item in enumerate(translated_data['results']['items']):
        if item['type'] == 'pronunciation':
            for alt in item['alternatives']:
                # Get the original content from the source data
                original = transcript_data['results']['items'][i]['alternatives'][0]['content']
                alt['original_content'] = original
    
    # 4. Add metadata about translation
    if 'metadata' not in translated_data:
        translated_data['metadata'] = {}
    
    translated_data['metadata']['translation'] = {
        'source_language': 'en',
        'target_language': 'pl',
        'translated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'bilingual': True
    }
    
    # Write the translated data
    print(f"Writing translated data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)
    
    print(f"Translation complete. Output saved to {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python translate_transcript.py transcript.json [output.json]")
        sys.exit(1)
    
    transcript_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        # Create default output filename by adding _pl to the input filename
        base, ext = os.path.splitext(transcript_file)
        output_file = f"{base}_pl{ext}"
    
    process_transcript(transcript_file, output_file)

if __name__ == "__main__":
    main()
EOF

# Make the script executable
chmod +x translate_transcript.py
```

## Running the Translation Script

```bash
# Install required Python packages
pip install boto3

# If using uv for Python package management
uv pip install boto3

# Run the script on your transcription file
python3 translate_transcript.py Lex_Fridman-Narendra_Modi_transcript.json Lex_Fridman-Narendra_Modi_transcript_pl.json

# Or if using uv
uv run translate_transcript.py Lex_Fridman-Narendra_Modi_transcript.json Lex_Fridman-Narendra_Modi_transcript_pl.json
```

### Handling Large Transcripts

The script has been enhanced to handle large transcripts that exceed AWS Translate's 10,000 byte limit per request. It now:

1. Breaks large texts into smaller chunks by paragraphs, sentences, or characters as needed
2. Translates each chunk separately
3. Reassembles the translated chunks while preserving the original order

If you're still encountering size issues with the full transcript, you can modify the process to translate smaller batches:

```python
# Modify in process_transcript function to translate smaller segments
# Instead of translating the entire transcript at once:

# Break the transcript text into paragraphs or sections
segments = transcript_text.split('\n\n')  # Or other logical break
translated_segments = []

for segment in segments:
    # Translate each segment individually
    translated = translate_large_text(segment, source_lang, target_lang)
    translated_segments.append(translated)
    # Add a small delay
    time.sleep(0.2)

# Reassemble the full translated text
full_translated_text = '\n\n'.join(translated_segments)
```

## Working with Speaker Labels (if applicable)

If your transcription includes speaker labels, you might want to preserve those as well. The script above preserves the structure but doesn't translate speaker specific segments separately.

To handle speaker segments, add this to the script:

```python
# Add to the process_transcript function
# After translating individual items

# Handle speaker segments if they exist
if 'speaker_labels' in transcript_data['results']:
    print("Processing speaker segments...")
    
    # Speaker labels themselves don't need translation, we just preserve them
    translated_data['results']['speaker_labels'] = transcript_data['results']['speaker_labels']
    
    # If you need to process speaker segments differently, add code here
```

## Creating Bilingual Subtitles

Once you have a translated transcript with preserved timestamps, you can create bilingual subtitles for video playback.

### Creating SRT Files

Create a script named `create_bilingual_srt.py`:

```bash
cat > create_bilingual_srt.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import os
import re

def format_time(seconds):
    """Convert seconds to SRT time format: HH:MM:SS,mmm"""
    hrs = int(seconds / 3600)
    seconds %= 3600
    mins = int(seconds / 60)
    seconds %= 60
    secs = int(seconds)
    msec = int((seconds - secs) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msec:03d}"

def merge_words_into_segments(items, max_chars=40, max_duration=5.0):
    """Group words into reasonably sized subtitle segments"""
    segments = []
    current_segment = {
        'words': [],
        'start_time': None,
        'end_time': None,
        'text': '',
        'original_text': ''
    }
    
    for item in items:
        if item['type'] == 'pronunciation':
            word = item['alternatives'][0]['content']
            original_word = item.get('alternatives', [{}])[0].get('original_content', word)
            start_time = float(item.get('start_time', 0))
            end_time = float(item.get('end_time', 0))
            
            # Start a new segment if this is the first word
            if current_segment['start_time'] is None:
                current_segment['start_time'] = start_time
            
            # Decide if we should start a new segment
            if (len(current_segment['text'] + ' ' + word) > max_chars or
                (current_segment['end_time'] is not None and 
                 end_time - current_segment['start_time'] > max_duration)):
                if current_segment['words']:  # Save non-empty segments
                    current_segment['text'] = ' '.join([w['word'] for w in current_segment['words']])
                    current_segment['original_text'] = ' '.join([w['original'] for w in current_segment['words']])
                    segments.append(current_segment)
                    
                # Start a new segment
                current_segment = {
                    'words': [],
                    'start_time': start_time,
                    'end_time': None,
                    'text': '',
                    'original_text': ''
                }
            
            # Add the word to the current segment
            current_segment['words'].append({'word': word, 'original': original_word})
            current_segment['end_time'] = end_time
            
        elif item['type'] == 'punctuation':
            if current_segment['words']:  # Only add punctuation if we have words
                punct = item['alternatives'][0]['content']
                # Add punctuation to the last word
                current_segment['words'][-1]['word'] += punct
                current_segment['words'][-1]['original'] += punct
    
    # Add the last segment if it has words
    if current_segment['words']:
        current_segment['text'] = ' '.join([w['word'] for w in current_segment['words']])
        current_segment['original_text'] = ' '.join([w['original'] for w in current_segment['words']])
        segments.append(current_segment)
    
    return segments

def create_bilingual_srt(translated_transcript_file, output_srt_file):
    """Create a bilingual SRT file from a translated transcript"""
    with open(translated_transcript_file, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)
    
    items = transcript_data['results']['items']
    segments = merge_words_into_segments(items)
    
    with open(output_srt_file, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments):
            # SRT index number
            f.write(f"{i+1}\n")
            
            # SRT timestamp line
            start_time_str = format_time(segment['start_time'])
            end_time_str = format_time(segment['end_time'])
            f.write(f"{start_time_str} --> {end_time_str}\n")
            
            # SRT content - original language in italics, then translated text
            f.write(f"<i>{segment['original_text']}</i>\n")
            f.write(f"{segment['text']}\n\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python create_bilingual_srt.py transcript_pl.json [output.srt]")
        sys.exit(1)
    
    transcript_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        # Create default output filename
        base = os.path.splitext(transcript_file)[0]
        output_file = f"{base}_bilingual.srt"
    
    create_bilingual_srt(transcript_file, output_file)
    print(f"Bilingual SRT file created: {output_file}")

if __name__ == "__main__":
    main()
EOF

# Make the script executable
chmod +x create_bilingual_srt.py
```

### Creating VTT Files

Create a script named `create_bilingual_vtt.py`:

```bash
cat > create_bilingual_vtt.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import os
import re

def format_time_vtt(seconds):
    """Convert seconds to VTT time format: HH:MM:SS.mmm"""
    hrs = int(seconds / 3600)
    seconds %= 3600
    mins = int(seconds / 60)
    seconds %= 60
    secs = int(seconds)
    msec = int((seconds - secs) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{msec:03d}"

def merge_words_into_segments(items, max_chars=40, max_duration=5.0):
    """Group words into reasonably sized subtitle segments"""
    # Function code identical to the SRT version
    segments = []
    current_segment = {
        'words': [],
        'start_time': None,
        'end_time': None,
        'text': '',
        'original_text': ''
    }
    
    for item in items:
        if item['type'] == 'pronunciation':
            word = item['alternatives'][0]['content']
            original_word = item.get('alternatives', [{}])[0].get('original_content', word)
            start_time = float(item.get('start_time', 0))
            end_time = float(item.get('end_time', 0))
            
            # Start a new segment if this is the first word
            if current_segment['start_time'] is None:
                current_segment['start_time'] = start_time
            
            # Decide if we should start a new segment
            if (len(current_segment['text'] + ' ' + word) > max_chars or
                (current_segment['end_time'] is not None and 
                 end_time - current_segment['start_time'] > max_duration)):
                if current_segment['words']:  # Save non-empty segments
                    current_segment['text'] = ' '.join([w['word'] for w in current_segment['words']])
                    current_segment['original_text'] = ' '.join([w['original'] for w in current_segment['words']])
                    segments.append(current_segment)
                    
                # Start a new segment
                current_segment = {
                    'words': [],
                    'start_time': start_time,
                    'end_time': None,
                    'text': '',
                    'original_text': ''
                }
            
            # Add the word to the current segment
            current_segment['words'].append({'word': word, 'original': original_word})
            current_segment['end_time'] = end_time
            
        elif item['type'] == 'punctuation':
            if current_segment['words']:  # Only add punctuation if we have words
                punct = item['alternatives'][0]['content']
                # Add punctuation to the last word
                current_segment['words'][-1]['word'] += punct
                current_segment['words'][-1]['original'] += punct
    
    # Add the last segment if it has words
    if current_segment['words']:
        current_segment['text'] = ' '.join([w['word'] for w in current_segment['words']])
        current_segment['original_text'] = ' '.join([w['original'] for w in current_segment['words']])
        segments.append(current_segment)
    
    return segments

def create_bilingual_vtt(translated_transcript_file, output_vtt_file):
    """Create a bilingual VTT file from a translated transcript"""
    with open(translated_transcript_file, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)
    
    items = transcript_data['results']['items']
    segments = merge_words_into_segments(items)
    
    with open(output_vtt_file, 'w', encoding='utf-8') as f:
        # VTT header
        f.write("WEBVTT\n\n")
        
        for i, segment in enumerate(segments):
            # VTT cue ID (optional)
            f.write(f"cue-{i+1}\n")
            
            # VTT timestamp line
            start_time_str = format_time_vtt(segment['start_time'])
            end_time_str = format_time_vtt(segment['end_time'])
            f.write(f"{start_time_str} --> {end_time_str}\n")
            
            # VTT content - original language in italics, then translated text
            f.write(f"<i>{segment['original_text']}</i>\n")
            f.write(f"{segment['text']}\n\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python create_bilingual_vtt.py transcript_pl.json [output.vtt]")
        sys.exit(1)
    
    transcript_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        # Create default output filename
        base = os.path.splitext(transcript_file)[0]
        output_file = f"{base}_bilingual.vtt"
    
    create_bilingual_vtt(transcript_file, output_file)
    print(f"Bilingual VTT file created: {output_file}")

if __name__ == "__main__":
    main()
EOF

# Make the script executable
chmod +x create_bilingual_vtt.py
```

## Complete Workflow for Translation and Subtitle Creation

```bash
# 1. Run the translation script to translate while preserving timestamps
python3 translate_transcript.py Lex_Fridman-Narendra_Modi_transcript.json

# Or with uv
uv run translate_transcript.py Lex_Fridman-Narendra_Modi_transcript.json

# 2. Create bilingual SRT subtitles
python3 create_bilingual_srt.py Lex_Fridman-Narendra_Modi_transcript_pl.json

# Or with uv
uv run create_bilingual_srt.py Lex_Fridman-Narendra_Modi_transcript_pl.json

# 3. Create bilingual VTT subtitles
python3 create_bilingual_vtt.py Lex_Fridman-Narendra_Modi_transcript_pl.json

# Or with uv
uv run create_bilingual_vtt.py Lex_Fridman-Narendra_Modi_transcript_pl.json
```

The updated script includes detailed progress output and better error handling, making it easier to monitor the translation process, especially for large files.

## Using AWS Batch Translation for Larger Projects

For larger projects with multiple transcription files, you can use AWS Batch Translation service:

```bash
# Create an S3 bucket folder for batch translation input
aws s3 mb s3://szaleju-bucket/batch-translate-input/

# Upload all transcription files
aws s3 cp . s3://szaleju-bucket/batch-translate-input/ --include "*_transcript.json"

# Start a batch translation job
aws translate start-text-translation-job \
    --job-name "TranscriptTranslationBatch" \
    --source-language-code en \
    --target-language-codes pl \
    --input-data-config "S3Uri=s3://szaleju-bucket/batch-translate-input/,ContentType=application/json" \
    --output-data-config "S3Uri=s3://szaleju-bucket/batch-translate-output/" \
    --data-access-role-arn "arn:aws:iam::ACCOUNT_ID:role/TranslateAccessRole"

# Check status of the batch job
aws translate describe-text-translation-job --job-id JOB_ID
```

## Troubleshooting

### Common Issues:

1. **Rate Limiting Errors**
   - AWS Translate has service quotas that limit the number of requests per second
   - Solution: Implement backoff/retry logic in the script or reduce batch size

2. **Large Text Translation Failures**
   - AWS Translate has a size limit per request (usually around 5,000 characters)
   - Solution: Break large segments into smaller chunks for translation

3. **Character Encoding Issues**
   - Ensure all files are saved with UTF-8 encoding to support Polish characters
   - Use `encoding='utf-8'` in file operations and `ensure_ascii=False` in JSON dumps

4. **Inconsistent Translation Quality**
   - AWS Translate might struggle with specialized terminology or context
   - Consider using custom terminology files for domain-specific translations

## Optimizing Translation Quality

### Custom Terminology

Create a CSV file with your custom terminology:

```bash
cat > custom_terms.csv << 'EOF'
en,pl
Lex Fridman,Lex Fridman
Narendra Modi,Narendra Modi
EOF

# Upload to S3
aws s3 cp custom_terms.csv s3://szaleju-bucket/terminology/

# Create the custom terminology in AWS Translate
aws translate import-terminology \
    --name "PodcastTerminology" \
    --terminology-data "File=s3://szaleju-bucket/terminology/custom_terms.csv,Format=CSV" \
    --description "Custom terminology for Lex Fridman podcasts"

# Use the custom terminology in translation
aws translate translate-text \
    --text "Hello world" \
    --source-language-code en \
    --target-language-code pl \
    --terminology-names "PodcastTerminology"
```

### Update the translation script to use custom terminology:

```python
# Add to the get_batch_translate function
translate.translate_text(
    Text=text,
    SourceLanguageCode=source_lang,
    TargetLanguageCode=target_lang,
    TerminologyNames=["PodcastTerminology"]  # Add this line
)
```

## Next Steps

After successful translation:
1. Validate the quality of translations
2. Convert to subtitle formats (SRT, VTT) for media players
3. Test playback with video files
4. Consider additional languages beyond Polish