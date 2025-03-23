# Converting JSON Transcript to SRT Subtitles

This guide describes how to convert a Polish transcript JSON file (from AWS Translate) to SRT (SubRip Text) subtitle format, which is widely used in videos and media players.

## JSON File Content

The `Lex_Fridman-Narendra_Modi_transcript_pl.json` file contains a transcript of Lex Fridman's interview with Narendra Modi, translated to Polish. The file includes:

- Full transcript text
- Individual words with their timestamps
- Confidence scores
- Original English content

## SRT Format

SRT format consists of a sequence of numbered blocks, each containing:

1. A sequential number (starting from 1)
2. Start and end timestamps in `HH:MM:SS,mmm --> HH:MM:SS,mmm` format
3. Subtitle text (one or more lines)
4. A blank line separating blocks

Example:
```
1
00:00:01,000 --> 00:00:04,000
To jest przykładowy napis
w formacie SRT.

2
00:00:04,500 --> 00:00:06,500
To jest drugi napis.
```

## Conversion Process

### Step 1: Install Required Packages

```bash
pip install srt datetime
```

### Step 2: Conversion Script

Create a file named `json_to_srt.py` with the following code:

```python
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

def group_words_into_subtitle_segments(items, max_chars=40, max_duration=5.0):
    """Groups words into subtitle segments of appropriate length"""
    segments = []
    current_segment = []
    current_char_count = 0
    segment_start_time = None
    
    for item in items:
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
            end_time = float(item['start_time'])
            
            # Check if the segment is too long in duration
            if end_time - segment_start_time > max_duration and len(current_segment) > 1:
                # If so, split it into smaller parts
                mid_point = len(current_segment) // 2
                first_half = ' '.join(current_segment[:mid_point])
                second_half = ' '.join(current_segment[mid_point:])
                
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
        segments.append(Segment(segment_start_time, end_time, segment_text))
    
    return segments

def create_srt_subtitles(segments):
    """Creates a list of SRT subtitle objects"""
    srt_subtitles = []
    
    for i, segment in enumerate(segments):
        start = datetime.timedelta(seconds=segment.start_time)
        end = datetime.timedelta(seconds=segment.end_time)
        
        subtitle = srt.Subtitle(
            index=i+1,  # SRT numbering starts at 1
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
```

### Step 3: Run the Conversion

```bash
python json_to_srt.py Lex_Fridman-Narendra_Modi_transcript_pl.json Lex_Fridman-Narendra_Modi_transcript_pl.srt
```

## Adjusting Subtitle Parameters

The script can be customized by modifying the parameters in the `group_words_into_subtitle_segments` function:
- `max_chars`: maximum number of characters in one subtitle line (default 40)
- `max_duration`: maximum duration of one subtitle in seconds (default 5.0)

## Code Explanation

1. **Loading JSON Data**: The script loads the JSON file containing the transcript.
2. **Grouping Words**: Words are grouped into subtitle segments considering optimal text length and display time.
3. **Creating SRT Subtitles**: Each segment is converted to an SRT subtitle object with appropriate timestamps.
4. **Saving SRT File**: Subtitles are composed in SRT format and saved to the output file.

## Notes

- The script ignores punctuation marks without timestamps and attaches them to the last word.
- Long text segments are split to ensure comfortable reading.
- You can adjust the maximum subtitle length and display time according to your needs.
- The AWS transcript contains both Polish and original English text - the script uses only the Polish version by default.

## Optional Enhancement: Adding Original English Text

If you'd like to include the original English text as well, you can modify the script to display both languages. Add the following function to the script:

```python
def group_bilingual_subtitle_segments(items, max_chars=40, max_duration=5.0):
    """Groups words into bilingual subtitle segments (Polish and English)"""
    segments = []
    current_segment_pl = []
    current_segment_en = []
    current_char_count = 0
    segment_start_time = None
    
    for item in items:
        # Skip punctuation marks without timestamps
        if item['type'] != 'pronunciation':
            if current_segment_pl:
                # Add punctuation to the last word
                punctuation = item['alternatives'][0]['content']
                current_segment_pl[-1] += punctuation
                
                # Also add to English if available
                if 'original_content' in item['alternatives'][0] and current_segment_en:
                    current_segment_en[-1] += item['alternatives'][0]['original_content']
            continue
            
        # Get word information
        word_pl = item['alternatives'][0]['content']
        word_en = item['alternatives'][0].get('original_content', word_pl)  # Fallback to Polish if no English
        start_time = float(item['start_time'])
        
        # If this is the first element of the segment, record its start time
        if not segment_start_time:
            segment_start_time = start_time
            
        # Check if adding this word would exceed the character limit
        if current_char_count + len(word_pl) + 1 > max_chars and current_segment_pl:
            # Create bilingual text
            segment_text_pl = ' '.join(current_segment_pl)
            segment_text_en = ' '.join(current_segment_en)
            bilingual_text = f"{segment_text_pl}\n[{segment_text_en}]"
            
            end_time = float(item['start_time'])
            segments.append(Segment(segment_start_time, end_time, bilingual_text))
            
            # Start a new segment
            current_segment_pl = [word_pl]
            current_segment_en = [word_en]
            current_char_count = len(word_pl)
            segment_start_time = start_time
        else:
            # Add the word to the current segment
            current_segment_pl.append(word_pl)
            current_segment_en.append(word_en)
            current_char_count += len(word_pl) + 1
        
        # Update the segment end time
        end_time = float(item['end_time'])
    
    # Add the last segment if it exists
    if current_segment_pl:
        segment_text_pl = ' '.join(current_segment_pl)
        segment_text_en = ' '.join(current_segment_en)
        bilingual_text = f"{segment_text_pl}\n[{segment_text_en}]"
        
        segments.append(Segment(segment_start_time, end_time, bilingual_text))
    
    return segments
```

Then replace the call to `group_words_into_subtitle_segments` with `group_bilingual_subtitle_segments` in the `json_to_srt` function to create bilingual subtitles.