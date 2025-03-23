#!/usr/bin/env python3
import json
import srt
import datetime
import re
from collections import namedtuple

# Structure to store speech segments
Segment = namedtuple('Segment', ['start_time', 'end_time', 'text'])


def parse_time(time_str):
    """Converts time string from JSON to datetime.timedelta object"""
    seconds = float(time_str)
    return datetime.timedelta(seconds=seconds)


def clean_segment_text(text):
    """Clean segment text by removing duplicate punctuation"""
    # Replace multiple periods with a single one
    text = re.sub(r'\.{2,}', '.', text)
    # Replace multiple commas with a single one
    text = re.sub(r',{2,}', ',', text)
    # Replace multiple exclamation marks with a single one
    text = re.sub(r'!{2,}', '!', text)
    # Replace multiple question marks with a single one
    text = re.sub(r'\?{2,}', '?', text)
    # Replace multiple semicolons with a single one
    text = re.sub(r';{2,}', ';', text)
    # Replace multiple colons with a single one
    text = re.sub(r':{2,}', ':', text)
    return text


def group_words_into_subtitle_segments(items, max_chars=40, max_duration=5.0):
    """Groups words into subtitle segments of appropriate length"""
    segments = []
    current_segment = []
    current_char_count = 0
    segment_start_time = None
    
    # Pre-process items to handle consecutive duplicate words and punctuation
    processed_items = []
    i = 0
    while i < len(items):
        # Handle duplicate pronunciation items (words)
        if items[i]['type'] == 'pronunciation' and i + 1 < len(items) and items[i+1]['type'] == 'pronunciation':
            word1 = items[i]['alternatives'][0]['content']
            word2 = items[i+1]['alternatives'][0]['content']
            
            # Check for duplicate words
            if word1.lower() == word2.lower():
                # Create a merged item with start time from first word and end time from second
                merged_item = items[i].copy()
                merged_item['end_time'] = items[i+1]['end_time']
                processed_items.append(merged_item)
                i += 2  # Skip both words
                continue
        
        # Handle duplicate punctuation
        if items[i]['type'] == 'punctuation' and i + 1 < len(items) and items[i+1]['type'] == 'punctuation':
            punct1 = items[i]['alternatives'][0]['content']
            punct2 = items[i+1]['alternatives'][0]['content']
            
            # Check for duplicate punctuation
            if punct1 == punct2:
                # Only keep the first one
                processed_items.append(items[i])
                i += 2  # Skip both punctuation marks
                continue
                
        # Normal processing for non-duplicates
        processed_items.append(items[i])
        i += 1
        
    # Continue with usual processing using the processed items
    for item in processed_items:
        # Skip punctuation marks without timestamps
        if item['type'] != 'pronunciation':
            if current_segment:
                # Add punctuation to the last word
                punctuation = item['alternatives'][0]['content']
                current_segment[-1] += punctuation
            continue

        # Get word information
        word = item['alternatives'][0]['content']
        start_time = float(item['start_time'])

        # If this is the first element of the segment, record its start time
        if not segment_start_time:
            segment_start_time = start_time

        # Check if adding this word would exceed the character limit
        if current_char_count + len(word) + 1 > max_chars and current_segment:  # +1 for space
            # Create a new segment from the collected words
            segment_text = ' '.join(current_segment)
            # Clean up any duplicate punctuation
            segment_text = clean_segment_text(segment_text)
            end_time = float(item['start_time'])

            # Check if the segment is too long in duration
            if end_time - segment_start_time > max_duration and len(current_segment) > 1:
                # If so, split it into smaller parts
                mid_point = len(current_segment) // 2
                first_half = ' '.join(current_segment[:mid_point])
                second_half = ' '.join(current_segment[mid_point:])
                
                # Clean up any duplicate punctuation
                first_half = clean_segment_text(first_half)
                second_half = clean_segment_text(second_half)

                # Estimate the midpoint time proportionally to text length
                mid_time = segment_start_time + (end_time - segment_start_time) * (len(first_half) / len(segment_text))

                segments.append(Segment(segment_start_time, mid_time, first_half))
                segments.append(Segment(mid_time, end_time, second_half))
            else:
                segments.append(Segment(segment_start_time, end_time, segment_text))

            # Start a new segment
            current_segment = [word]
            current_char_count = len(word)
            segment_start_time = start_time
        else:
            # Add the word to the current segment
            current_segment.append(word)
            current_char_count += len(word) + 1  # +1 for space

        # Update the segment end time
        end_time = float(item['end_time'])

    # Add the last segment if it exists
    if current_segment:
        segment_text = ' '.join(current_segment)
        # Clean up any duplicate punctuation
        segment_text = clean_segment_text(segment_text)
        segments.append(Segment(segment_start_time, end_time, segment_text))

    return segments


def create_srt_subtitles(segments):
    """Creates a list of SRT subtitle objects"""
    srt_subtitles = []

    for i, segment in enumerate(segments):
        start = datetime.timedelta(seconds=segment.start_time)
        end = datetime.timedelta(seconds=segment.end_time)

        subtitle = srt.Subtitle(
            index=i + 1,  # SRT numbering starts at 1
            start=start,
            end=end,
            content=segment.text
        )

        srt_subtitles.append(subtitle)

    return srt_subtitles


def json_to_srt(json_file, srt_file):
    """Converts transcript JSON file to SRT file"""
    print(f"Processing file {json_file}...")

    # Load JSON data
    with open(json_file, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)

    # Get transcript items
    items = transcript_data['results']['items']

    # Group words into subtitle segments
    segments = group_words_into_subtitle_segments(items)

    # Create SRT subtitles
    srt_subtitles = create_srt_subtitles(segments)

    # Save the SRT file
    with open(srt_file, 'w', encoding='utf-8') as f:
        f.write(srt.compose(srt_subtitles))

    print(f"Conversion complete. Subtitles saved to {srt_file}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python json_to_srt.py transcript_file.json [output_file.srt]")
        sys.exit(1)

    json_file = sys.argv[1]

    if len(sys.argv) > 2:
        srt_file = sys.argv[2]
    else:
        # Create default output filename
        import os

        base, _ = os.path.splitext(json_file)
        srt_file = f"{base}.srt"

    json_to_srt(json_file, srt_file)