# !/usr/bin/env python3
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
        batch = texts[i:i + batch_size]
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
        print(
            f"Translating transcript segment {i + 1}/{len(transcripts)} ({len(transcript_text.encode('utf-8'))} bytes)")

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
        batch = word_contents[i:i + batch_size]
        batch_indices = word_indices[i:i + batch_size]

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
