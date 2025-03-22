#!/usr/bin/env python3
import json
import boto3
import time
import sys
import os
from concurrent.futures import ThreadPoolExecutor

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
                
                future = executor.submit(
                    translate.translate_text,
                    Text=text,
                    SourceLanguageCode=source_lang,
                    TargetLanguageCode=target_lang
                )
                futures.append(future)
            
            # Collect results as they complete
            for future in futures:
                try:
                    response = future.result()
                    batch_results.append(response['TranslatedText'])
                except Exception as e:
                    print(f"Error translating text: {e}")
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
    
    # 1. Translate the full transcript
    transcripts = transcript_data['results']['transcripts']
    transcript_texts = [t['transcript'] for t in transcripts]
    translated_transcripts = get_batch_translate(transcript_texts)
    
    for i, translated_text in enumerate(translated_transcripts):
        translated_data['results']['transcripts'][i]['transcript'] = translated_text
    
    # 2. Translate individual items (words, etc.)
    items = transcript_data['results']['items']
    
    # Collect all word contents that need translation
    word_indices = []
    word_contents = []
    
    for i, item in enumerate(items):
        # Only translate pronunciation items (actual words), not punctuation
        if item['type'] == 'pronunciation':
            alternatives = item['alternatives']
            for alt_idx, alt in enumerate(alternatives):
                word_indices.append((i, alt_idx))
                word_contents.append(alt['content'])
    
    # Batch translate all words
    translated_words = get_batch_translate(word_contents)
    
    # Replace word contents with translations
    for (item_idx, alt_idx), translated_word in zip(word_indices, translated_words):
        translated_data['results']['items'][item_idx]['alternatives'][alt_idx]['content'] = translated_word
    
    # 3. Add original_content field to keep both languages
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

