# Audio Preparation Guide

This guide provides instructions for preparing audio files for transcription and translation using AWS services.

## Audio Format Requirements

### AWS Transcribe Supported Formats
- FLAC
- MP3
- MP4
- WAV
- AMR
- OGG
- WebM
- M4A (AAC codec)

### Recommended Format
Use MP3 or MP4 formats for best compatibility and file size efficiency:
- Sample rate: 16,000 Hz or higher (44,100 Hz recommended for high quality)
- Bit rate: 128 kbps or higher
- Channels: 1 (mono) or 2 (stereo)

## Pre-Processing Steps

### 1. Rename Files to Remove Spaces

**Important**: Spaces in filenames can cause issues with AWS CLI commands, S3 paths, and URL encoding. Renaming files to use underscores or hyphens instead of spaces is highly recommended.

Spaces in filenames can cause issues with AWS CLI and other command-line tools. It's recommended to rename files to replace spaces with underscores or hyphens:

```bash
# Rename using mv command
mv "Lex Fridman - Narendra Modi.m4a" "Lex_Fridman-Narendra_Modi.m4a"
mv "Lex Fridman - Narendra Modi.mp4" "Lex_Fridman-Narendra_Modi.mp4"

# Alternative method using find and rename (if multiple files)
find . -name "* *" -type f -print0 | xargs -0 rename 's/ /_/g'
```

### 2. Inspect Your Audio File
```bash
# Check audio file details (using renamed file)
ffprobe -i Lex_Fridman-Narendra_Modi.m4a

# Alternative using mediainfo
mediainfo Lex_Fridman-Narendra_Modi.m4a
```

### 3. Convert to Optimal Format (if needed)
```bash
# Convert to MP3 (if not already in a supported format)
ffmpeg -i Lex_Fridman-Narendra_Modi.m4a -vn -ar 44100 -ac 2 -b:a 192k Lex_Fridman-Narendra_Modi.mp3

# Convert to WAV for highest quality (larger file)
ffmpeg -i Lex_Fridman-Narendra_Modi.m4a -vn -ar 44100 Lex_Fridman-Narendra_Modi.wav
```

### 4. Audio Enhancement (Optional)
```bash
# Normalize audio levels
ffmpeg -i Lex_Fridman-Narendra_Modi.mp3 -af "volume=2.0" -ar 44100 -b:a 192k Lex_Fridman-Narendra_Modi_normalized.mp3

# Noise reduction (if needed)
ffmpeg -i Lex_Fridman-Narendra_Modi.mp3 -af "highpass=f=200,lowpass=f=8000" -ar 44100 -b:a 192k Lex_Fridman-Narendra_Modi_filtered.mp3
```

### 5. Split Large Files (if needed)
AWS Transcribe has a file size limit of 2GB. If your file exceeds this limit:

```bash
# Split audio into 30-minute segments
ffmpeg -i Lex_Fridman-Narendra_Modi.mp3 -f segment -segment_time 1800 -c copy Lex_Fridman-Narendra_Modi_part%03d.mp3
```

## S3 Bucket Setup and Upload

### 1. Verify the S3 Bucket Exists
```bash
# List all available buckets
aws s3 ls
```

The output should include `szaleju-bucket` if it already exists.

### 2. Upload Audio File to S3 with Prefix
```bash
# Upload a single file with translate/ prefix
aws s3 cp Lex_Fridman-Narendra_Modi.m4a s3://szaleju-bucket/translate/

# If you converted the file, upload the converted version
aws s3 cp Lex_Fridman-Narendra_Modi.mp3 s3://szaleju-bucket/translate/
```

### 3. Verify File Upload
```bash
# List files in the translate/ prefix
aws s3 ls s3://szaleju-bucket/translate/

# Get file details
aws s3api head-object --bucket szaleju-bucket --key translate/Lex_Fridman-Narendra_Modi.m4a
```

### 4. Set Appropriate File Permissions
If the bucket policy isn't already configured for AWS Transcribe access:

```bash
# Make sure the file is accessible to AWS Transcribe
aws s3api put-object-acl --bucket szaleju-bucket --key translate/Lex_Fridman-Narendra_Modi.m4a --acl private
```

## Additional S3 Management Options

### 1. Add Metadata to Audio Files
```bash
aws s3api copy-object \
    --bucket szaleju-bucket \
    --copy-source szaleju-bucket/translate/podcasts/lex-fridman/Lex_Fridman-Narendra_Modi.m4a \
    --key translate/Lex_Fridman-Narendra_Modi.m4a \
    --metadata '{"speaker":"Narendra Modi","interviewer":"Lex Fridman","language":"en","topic":"politics"}' 
```

### 2. Create Additional Organization with Folders
For better organization, you can use additional prefixes:

```bash
aws s3 cp Lex_Fridman-Narendra_Modi.m4a s3://szaleju-bucket/translate/podcasts/lex-fridman/
```

### 3. Generate Pre-signed URL (if needed)
To share the audio file temporarily:

```bash
aws s3 presign s3://szaleju-bucket/translate/Lex_Fridman-Narendra_Modi.m4a --expires-in 3600
```

## Troubleshooting

### Upload Issues
- **Error: "Access Denied"**: Verify your AWS credentials and permissions
  ```bash
  aws sts get-caller-identity
  ```

- **Slow Upload**: For large files, consider using multipart uploads
  ```bash
  aws s3 cp Lex_Fridman-Narendra_Modi.m4a s3://szaleju-bucket/translate/ --expected-size $(wc -c < Lex_Fridman-Narendra_Modi.m4a)
  ```

### File Format Issues
If AWS Transcribe doesn't accept your format despite being listed as supported:
- Check the codec used in the container (use `ffprobe`)
- Convert to a widely supported format like MP3 using the commands provided earlier

### Quick File Check
Before uploading, ensure your audio file is valid:
```bash
ffplay Lex_Fridman-Narendra_Modi.m4a -nodisp
```

## AWS Transcribe Format Compatibility Notes

- **M4A files**: Must use AAC codec (most do)
- **MP4 files**: Must contain audio track
- **Maximum duration**: 14 hours
- **Maximum file size**: 2 GB
- **Sample rates**: 8,000 Hz to 48,000 Hz (higher is better for quality)

## Next Steps

After successfully uploading your audio file, you can proceed to:
1. Start an AWS Transcribe job pointing to your S3 file path
2. Retrieve the transcription results
3. Translate the transcribed text to Polish using AWS Translate
4. Generate subtitle files in required formats
