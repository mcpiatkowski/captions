# AWS Transcribe Guide

This guide provides step-by-step instructions for transcribing audio files using AWS Transcribe service via the AWS CLI.

## Prerequisites

Before starting the transcription process, ensure you have:

1. Properly configured AWS CLI with appropriate credentials
2. Audio file already uploaded to S3 bucket (as detailed in AUDIO_PREPARATION.md)
3. Necessary permissions to access AWS Transcribe and S3 services

## Starting a Transcription Job

### 1. Basic Transcription Job

```bash
# Start a basic transcription job
aws transcribe start-transcription-job \
    --transcription-job-name "LexFridman_Modi_Interview" \
    --language-code en-US \
    --media-format m4a \
    --media "MediaFileUri=s3://szaleju-bucket/translate/podcasts/lex-fridman/Lex_Fridman-Narendra_Modi.m4a" \
    --output-bucket-name "szaleju-bucket" \
    --output-key "transcribe-output/podcasts/lex-fridman/Lex_Fridman-Narendra_Modi_transcript.json"
```

### 2. Advanced Transcription with Speaker Identification

For interviews with multiple speakers (like the Lex Fridman podcast):

```bash
# Start transcription with speaker identification
aws transcribe start-transcription-job \
    --transcription-job-name "LexFridman_Modi_Interview_Speakers" \
    --language-code en-US \
    --media-format m4a \
    --media "MediaFileUri=s3://szaleju-bucket/translate/Lex_Fridman-Narendra_Modi.m4a" \
    --output-bucket-name "szaleju-bucket" \
    --output-key "transcribe-output/Lex_Fridman-Narendra_Modi_transcript_speakers.json" \
    --show-speaker-labels \
    --max-speaker-labels 2 \
    --settings "VocabularyName=tech-terms,ShowAlternatives=true,MaxAlternatives=2"
```

### 3. Custom Vocabulary (Optional)

If there are specialized terms or names that AWS Transcribe might struggle with:

```bash
# First, create a custom vocabulary file (vocab.txt)
echo "Narendra Modi
Lex Fridman
Artificial Intelligence
Machine Learning" > vocab.txt

# Upload to S3
aws s3 cp vocab.txt s3://szaleju-bucket/vocab/tech-terms.txt

# Create a custom vocabulary
aws transcribe create-vocabulary \
    --vocabulary-name "tech-terms" \
    --language-code en-US \
    --vocabulary-file-uri "s3://szaleju-bucket/vocab/tech-terms.txt"
```

Then use it in your transcription job with the `--settings "VocabularyName=tech-terms"` parameter.

## Monitoring Transcription Jobs

### 1. List All Transcription Jobs

```bash
# List all transcription jobs
aws transcribe list-transcription-jobs

# List jobs with specific status
aws transcribe list-transcription-jobs --status IN_PROGRESS
aws transcribe list-transcription-jobs --status COMPLETED
aws transcribe list-transcription-jobs --status FAILED
```

### 2. Get Details of a Specific Job

```bash
# Get job details
aws transcribe get-transcription-job --transcription-job-name "LexFridman_Modi_Interview"
```

### 3. Wait for Completion

```bash
# Wait for job completion (use in scripts)
aws transcribe wait transcription-job-completed --transcription-job-name "LexFridman_Modi_Interview"

# Or check status in a loop
while true; do
    status=$(aws transcribe get-transcription-job --transcription-job-name "LexFridman_Modi_Interview" --query "TranscriptionJob.TranscriptionJobStatus" --output text)
    echo "Job status: $status"
    if [ "$status" != "IN_PROGRESS" ]; then
        break
    fi
    sleep 30
done
```

## Retrieving Transcription Results

### 1. Get Transcription Results

Once the job completes, get the results:

```bash
# Download the transcription JSON file
aws s3 cp s3://szaleju-bucket/transcribe-output/podcasts/lex-fridman/Lex_Fridman-Narendra_Modi_transcript.json .
```

### 2. Extract Pure Text (if needed)

```bash
# Extract only the transcript text using jq (if installed)
jq -r '.results.transcripts[0].transcript' Lex_Fridman-Narendra_Modi_transcript.json > Lex_Fridman-Narendra_Modi_text.txt

# Alternative method using Python
python -c "import json; file = open('Lex_Fridman-Narendra_Modi_transcript.json', 'r'); data = json.load(file); print(data['results']['transcripts'][0]['transcript'])" > Lex_Fridman-Narendra_Modi_text.txt
```

### 3. Extract Time-Stamped Words (for subtitles)

```bash
# Extract all words with timestamps using jq
jq -r '.results.items[] | select(.type=="pronunciation") | [.start_time, .end_time, .alternatives[0].content] | @tsv' Lex_Fridman-Narendra_Modi_transcript.json > Lex_Fridman-Narendra_Modi_words.tsv
```

## Advanced Features

### 1. Channel Identification (for stereo audio)

If your audio has separate channels for different speakers:

```bash
aws transcribe start-transcription-job \
    --transcription-job-name "LexFridman_Modi_Interview_Channels" \
    --language-code en-US \
    --media-format m4a \
    --media "MediaFileUri=s3://szaleju-bucket/translate/Lex_Fridman-Narendra_Modi.m4a" \
    --output-bucket-name "szaleju-bucket" \
    --output-key "transcribe-output/Lex_Fridman-Narendra_Modi_channels.json" \
    --settings "ChannelIdentification=true"
```

### 2. Content Redaction (for sensitive information)

To automatically redact personally identifiable information:

```bash
aws transcribe start-transcription-job \
    --transcription-job-name "LexFridman_Modi_Interview_Redacted" \
    --language-code en-US \
    --media-format m4a \
    --media "MediaFileUri=s3://szaleju-bucket/translate/Lex_Fridman-Narendra_Modi.m4a" \
    --output-bucket-name "szaleju-bucket" \
    --output-key "transcribe-output/Lex_Fridman-Narendra_Modi_redacted.json" \
    --content-redaction "RedactionType=PII,RedactionOutput=redacted"
```

### 3. Custom Language Models (for domain-specific audio)

For specialized content, custom language models can improve accuracy:

```bash
# First, create a custom language model (requires existing training data)
aws transcribe create-language-model \
    --base-model-name "NarrowBand" \
    --model-name "PodcastsModel" \
    --language-code en-US \
    --input-data-config "S3Uri=s3://szaleju-bucket/training-data/,TuningDataS3Uri=s3://szaleju-bucket/tuning-data/,DataAccessRoleArn=arn:aws:iam::ACCOUNT_ID:role/TranscribeAccess"

# Use the custom language model
aws transcribe start-transcription-job \
    --transcription-job-name "LexFridman_Modi_Interview_CustomModel" \
    --language-code en-US \
    --media-format m4a \
    --media "MediaFileUri=s3://szaleju-bucket/translate/Lex_Fridman-Narendra_Modi.m4a" \
    --output-bucket-name "szaleju-bucket" \
    --output-key "transcribe-output/Lex_Fridman-Narendra_Modi_custom.json" \
    --language-model-name "PodcastsModel"
```

## Handling Large Audio Files

For very long recordings, consider:

1. Breaking the audio into smaller chunks (see AUDIO_PREPARATION.md)
2. Using batch transcription for multiple files
3. Extending timeout values in your scripts

```bash
# Script to transcribe multiple audio segments
for segment in $(ls Lex_Fridman-Narendra_Modi_part*.mp3); do
    job_name=$(echo $segment | sed 's/.mp3/_job/g' | sed 's/[.-]/_/g')
    
    aws transcribe start-transcription-job \
        --transcription-job-name "$job_name" \
        --language-code en-US \
        --media-format mp3 \
        --media "MediaFileUri=s3://szaleju-bucket/translate/$segment" \
        --output-bucket-name "szaleju-bucket" \
        --output-key "transcribe-output/${segment%.mp3}.json"
        
    echo "Started job $job_name for $segment"
done
```

## Troubleshooting

### Common Issues:

1. **Job Fails with "AccessDenied"**
   - Check IAM permissions for both S3 and Transcribe
   - Verify S3 bucket policy allows Transcribe service access

2. **Unsupported Media Format**
   - Ensure the media format specified matches the actual file format
   - Convert file to a supported format (MP3, MP4, WAV, etc.)
   
3. **Poor Transcription Quality**
   - Try using a custom vocabulary for specialized terms
   - Consider using a custom language model
   - Check audio quality and consider pre-processing (noise reduction)

4. **Job Stuck in Queue**
   - Check AWS Transcribe service quotas and limits
   - Reduce file size or break into smaller segments

## Next Steps

After successful transcription:
1. Proceed to translation of the transcription text (see TRANSLATION.md)
2. Convert the transcription to subtitle formats for media players
3. Synchronize subtitles with the video file
