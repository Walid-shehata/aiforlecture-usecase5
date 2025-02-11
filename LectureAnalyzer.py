import streamlit as st
import boto3
import os
import json
from dotenv import load_dotenv
from subjects import get_subjects
from chapters import get_chapters
import requests
import uuid
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.units import inch


load_dotenv()

# Initialize AWS clients
s3 = boto3.client('s3',
                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                  region_name=os.getenv('AWS_REGION')
                  )

transcribe = boto3.client('transcribe',
                          aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                          region_name=os.getenv('AWS_REGION')
                          )

bedrock_runtime = boto3.client('bedrock-runtime',
                               aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                               aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                               region_name=os.getenv('AWS_REGION')
                               )

SOURCE_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
MEDIA_BUCKET_NAME = os.getenv('S3_ARTIFACTS_BUCKET_NAME')

def generate_pdf(subject, chapter, video_name, summary):
    buffer = io.BytesIO()

    def add_border_and_logo(canvas, doc):
        canvas.saveState()
        # Add border
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(3)
        canvas.rect(20, 20, letter[0] - 40, letter[1] - 40)

        # Add logo
        logo_path = "logo.png"
        logo_width = 1.5 * inch
        logo_height = 1.5 * inch
        canvas.drawImage(logo_path, letter[0] - logo_width - 0.5 * inch, 0.5 * inch, width=logo_width,
                         height=logo_height)

        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)

    styles = getSampleStyleSheet()

    # Modify the 'Normal' style for body text
    styles['Normal'].fontSize = 12
    styles['Normal'].leading = 14
    styles['Normal'].spaceAfter = 10  # Add space after each paragraph

    # Custom styles
    styles.add(ParagraphStyle(name='UniversityName', fontSize=20, textColor=colors.darkorange, spaceAfter=10))
    styles.add(ParagraphStyle(name='PoweredBy', fontSize=12, textColor=colors.black, spaceAfter=20))
    styles.add(ParagraphStyle(name='SubjectChapter', fontSize=15, textColor=colors.darkgreen, bold=True, spaceAfter=8))
    styles.add(ParagraphStyle(name='Topic', fontSize=13, textColor=colors.darkred, bold=True, spaceAfter=15))

    story = []

    # Add university name and "Powered by" paragraphs
    story.append(Paragraph("AnyUniversity", styles['UniversityName']))
    story.append(Paragraph("Powered By Amazon Bedrock", styles['PoweredBy']))

    # Add subject and chapter
    story.append(Paragraph(f"Subject Name: {subject}", styles['SubjectChapter']))
    story.append(Paragraph(f"Chapter Name: {chapter}", styles['SubjectChapter']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=15))

    # Add video name
    story.append(Paragraph(f"Video Name: {video_name}", styles['Topic']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=15))

    # Split the summary into paragraphs and add them individually
    paragraphs = summary.split('\n\n')
    for para in paragraphs:
        story.append(Paragraph(para.strip(), styles['Normal']))

    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=15))

    # Add space at the bottom of each page for the logo
    story.append(Spacer(1, 2 * inch))

    # Build the PDF
    doc.build(story, onFirstPage=add_border_and_logo, onLaterPages=add_border_and_logo)

    buffer.seek(0)
    return buffer

def save_pdf_asset(subject, chapter, video_name, content):
    folder_path = f"{subject}/{chapter}/DeliveredLectures/{video_name}"
    ensure_folder_exists(MEDIA_BUCKET_NAME, folder_path)
    key = f"{folder_path}/summary.pdf"
    s3.put_object(Bucket=MEDIA_BUCKET_NAME, Key=key, Body=content.getvalue())


def get_video_url(bucket, key):
    return s3.generate_presigned_url('get_object',
                                     Params={'Bucket': bucket,
                                             'Key': key},
                                     ExpiresIn=3600)



def ensure_folder_exists(bucket, folder_path):
    try:
        s3.put_object(Bucket=bucket, Key=(folder_path + '/'))
    except Exception as e:
        print(f"Error creating folder {folder_path}: {str(e)}")


def get_video_files(subject, chapter):
    prefix = f"{subject}/{chapter}/DeliveredLectures/"
    ensure_folder_exists(MEDIA_BUCKET_NAME, prefix)
    response = s3.list_objects_v2(Bucket=MEDIA_BUCKET_NAME, Prefix=prefix)
    video_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith(('.mp4', '.avi', '.mov'))]
    return video_files


def create_transcription(video_file):
    # Generate a unique job name by including a UUID
    job_name = f"transcribe_{os.path.basename(video_file)}_{uuid.uuid4().hex[:8]}"
    job_uri = f"s3://{MEDIA_BUCKET_NAME}/{video_file}"

    try:
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': job_uri},
            MediaFormat='mp4',
            LanguageCode='en-US'
        )

        while True:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                break

        if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
            result = requests.get(status['TranscriptionJob']['Transcript']['TranscriptFileUri'])
            return result.json()['results']['transcripts'][0]['transcript']
        else:
            return None
    except Exception as e:
        print(f"Error in transcription job: {str(e)}")
        return None


def generate_summary(transcript):
    prompt = f"Human: Summarize the following lecture transcript:\n\n{transcript}\n\nAssistant: Here's a summary of the lecture transcript:"
    response = bedrock_runtime.invoke_model(
        modelId="anthropic.claude-v2",
        body=json.dumps({
            "prompt": prompt,
            "max_tokens_to_sample": 500,
            "temperature": 0.5,
            "top_p": 1,
            "stop_sequences": ["\n\nHuman:"]
        })
    )
    return json.loads(response['body'].read())['completion']


def generate_flashcards(transcript):
    prompt = f"Human: Create 5 flashcards with key statements from this lecture transcript. Format each flashcard as 'Front: [content]' and 'Back: [content]' on separate lines:\n\n{transcript}\n\nAssistant: Here are 5 flashcards based on the lecture transcript:"
    response = bedrock_runtime.invoke_model(
        modelId="anthropic.claude-v2",
        body=json.dumps({
            "prompt": prompt,
            "max_tokens_to_sample": 500,
            "temperature": 0.5,
            "top_p": 1,
            "stop_sequences": ["\n\nHuman:"]
        })
    )
    flashcards_text = json.loads(response['body'].read())['completion']

    # Parse the flashcards into a list of dictionaries
    flashcards = []
    current_card = {}
    for line in flashcards_text.split('\n'):
        if line.startswith('Front:'):
            if current_card:
                flashcards.append(current_card)
                current_card = {}
            current_card['front'] = line[6:].strip()
        elif line.startswith('Back:'):
            current_card['back'] = line[5:].strip()
    if current_card:
        flashcards.append(current_card)

    return flashcards


def extract_assignments(transcript):
    prompt = f"Human: Extract any assignments or homework mentioned in this lecture transcript:\n\n{transcript}\n\nAssistant: Here are the assignments or homework mentioned in the lecture transcript:"
    response = bedrock_runtime.invoke_model(
        modelId="anthropic.claude-v2",
        body=json.dumps({
            "prompt": prompt,
            "max_tokens_to_sample": 500,
            "temperature": 0.5,
            "top_p": 1,
            "stop_sequences": ["\n\nHuman:"]
        })
    )
    return json.loads(response['body'].read())['completion']



def save_asset(subject, chapter, video_name, asset_type, content):
    folder_path = f"{subject}/{chapter}/DeliveredLectures/{video_name}"
    ensure_folder_exists(MEDIA_BUCKET_NAME, folder_path)
    if asset_type == 'flashcards':
        for i, card in enumerate(content):
            key = f"{folder_path}/flashcard_{i+1}.json"
            s3.put_object(Bucket=MEDIA_BUCKET_NAME, Key=key, Body=json.dumps(card))
    else:
        key = f"{folder_path}/{asset_type}.txt"
        s3.put_object(Bucket=MEDIA_BUCKET_NAME, Key=key, Body=content.encode('utf-8'))



def get_asset(subject, chapter, video_name, asset_type):
    if asset_type == 'flashcards':
        folder_path = f"{subject}/{chapter}/DeliveredLectures/{video_name}"
        flashcards = []
        i = 1
        while True:
            key = f"{folder_path}/flashcard_{i}.json"
            try:
                response = s3.get_object(Bucket=MEDIA_BUCKET_NAME, Key=key)
                flashcards.append(json.loads(response['Body'].read().decode('utf-8')))
                i += 1
            except s3.exceptions.NoSuchKey:
                break
        return flashcards if flashcards else None
    else:
        key = f"{subject}/{chapter}/DeliveredLectures/{video_name}/{asset_type}.txt"
        try:
            response = s3.get_object(Bucket=MEDIA_BUCKET_NAME, Key=key)
            return response['Body'].read().decode('utf-8')
        except s3.exceptions.NoSuchKey:
            return None


def flashcard_html(front, back):
    return f"""
    <style>
        .flashcard {{
            perspective: 1000px;
            width: 300px;
            height: 200px;
            margin: 20px auto;
        }}
        .flashcard-inner {{
            position: relative;
            width: 100%;
            height: 100%;
            text-align: center;
            transition: transform 0.6s;
            transform-style: preserve-3d;
        }}
        .flashcard:hover .flashcard-inner {{
            transform: rotateY(180deg);
        }}
        .flashcard-front, .flashcard-back {{
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            padding: 20px;
            box-sizing: border-box;
        }}
        .flashcard-front {{
            background-color: #f0f0f0;
            color: #333;
        }}
        .flashcard-back {{
            background-color: #3498db;
            color: white;
            transform: rotateY(180deg);
        }}
    </style>
    <div class="flashcard">
        <div class="flashcard-inner">
            <div class="flashcard-front">
                <p>{front}</p>
            </div>
            <div class="flashcard-back">
                <p>{back}</p>
            </div>
        </div>
    </div>
    """

def lecture_analyzer():
    with st.expander("📚 Click here for Tool Instructions"):
        st.markdown("""
        **How to use the Lecture-Analyzer:**
        1. Select a subject and chapter from the dropdown menus.
        2. Choose an action: "View Existing Videos" or "Upload New Video".
        >For viewing existing videos:
        a. Select a video from the list.
        b. View the video using the embedded player.
        c. Explore existing assets (transcription, summary, flashcards, assignments) in the expandable sections.
        d. Edit and save changes to existing assets if needed.
        e. Download assets in various formats (TXT, PDF) using the provided buttons.
        f. Generate new assets using the buttons under "Create New Assets":
           - Transcript: Creates a text version of the video's audio.
           - Summary: Generates a concise overview of the lecture content.
           - Flashcards: Creates study cards based on key points from the lecture.
           - Assignments: Extracts potential homework or tasks mentioned in the lecture.
        >For uploading a new video:
        a. Click on "Choose a video file" to select a video from your device.
        b. The video will be uploaded and added to the list of existing videos.

        Note: Generating new assets requires the transcript to be created first. The process may take a few moments, so please be patient when using these features.
        """)
    subjects = [""] + get_subjects()
    subject = st.selectbox("Select Subject", subjects, key="Lecture Analyzer Subject Selector")

    if subject:
        chapters = [""] + get_chapters(subject)
        chapter = st.selectbox("Select Chapter", chapters, key="Lecture Analyzer Chapter Selector")

        if chapter:
            action = st.radio("Choose an action:", ["View Existing Videos", "Upload New Video"])

            if action == "View Existing Videos":
                video_files = get_video_files(subject, chapter)

                if video_files:
                    selected_video = st.selectbox("Select Video", video_files, key="Lecture Analyzer Video Selector")

                    if selected_video:
                        video_name = os.path.basename(selected_video)

                        # Generate presigned URL for the video
                        video_url = get_video_url(MEDIA_BUCKET_NAME, selected_video)

                        # Display video player
                        st.subheader("Video Player")
                        st.video(video_url)

                        # Display existing assets
                        st.subheader("Existing Assets")
                        asset_types = ['transcription', 'summary', 'flashcards', 'assignments']
                        for asset_type in asset_types:
                            content = get_asset(subject, chapter, video_name, asset_type)
                            if content:
                                if asset_type == 'flashcards':
                                    with st.expander(f"Flashcards (click to view/edit)"):
                                        for i, card in enumerate(content):
                                            st.markdown(flashcard_html(card['front'], card['back']), unsafe_allow_html=True)
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                front = st.text_area(f"Edit Front", value=card['front'], height=100, key=f"flashcard_front_{i}")
                                            with col2:
                                                back = st.text_area(f"Edit Back", value=card['back'], height=100, key=f"flashcard_back_{i}")
                                            card['front'] = front
                                            card['back'] = back
                                        if st.button("Save Changes to Flashcards"):
                                            save_asset(subject, chapter, video_name, 'flashcards', content)
                                            st.success("Flashcards updated successfully!")

                                        # Add download button for flashcards
                                        flashcards_text = "\n\n".join([f"Flashcard {i+1}\nFront: {card['front']}\nBack: {card['back']}" for i, card in enumerate(content)])
                                        st.download_button(
                                            label="Download Flashcards",
                                            data=flashcards_text,
                                            file_name=f"{video_name}_flashcards.txt",
                                            mime="text/plain"
                                        )
                                else:
                                    with st.expander(f"{asset_type.capitalize()} (click to view/edit)"):
                                        edited_content = st.text_area(f"Edit {asset_type}", value=content, height=300, key=f"edit_{asset_type}")
                                        if st.button(f"Save Changes to {asset_type.capitalize()}"):
                                            save_asset(subject, chapter, video_name, asset_type, edited_content)
                                            if asset_type in ['summary', 'assignments']:
                                                pdf_buffer = generate_pdf(subject, chapter, video_name, edited_content)
                                                save_pdf_asset(subject, chapter, video_name, pdf_buffer)
                                            st.success(f"{asset_type.capitalize()} updated successfully!")

                                        # Add download buttons
                                        if asset_type in ['summary', 'assignments']:
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                st.download_button(
                                                    label=f"Download {asset_type} (TXT)",
                                                    data=edited_content,
                                                    file_name=f"{video_name}_{asset_type}.txt",
                                                    mime="text/plain"
                                                )
                                            with col2:
                                                pdf_buffer = generate_pdf(subject, chapter, video_name, edited_content)
                                                st.download_button(
                                                    label=f"Download {asset_type} (PDF)",
                                                    data=pdf_buffer,
                                                    file_name=f"{video_name}_{asset_type}.pdf",
                                                    mime="application/pdf"
                                                )
                                        else:
                                            st.download_button(
                                                label=f"Download {asset_type}",
                                                data=edited_content,
                                                file_name=f"{video_name}_{asset_type}.txt",
                                                mime="text/plain"
                                            )

                        st.subheader("Create New Assets")
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            if st.button("Generate Transcript"):
                                with st.spinner("Generating transcript..."):
                                    transcript = create_transcription(selected_video)
                                    if transcript:
                                        save_asset(subject, chapter, video_name, 'transcription', transcript)
                                        st.success("Transcript generated and saved successfully!")
                                        st.rerun()

                        with col2:
                            if st.button("Generate Summary"):
                                with st.spinner("Generating summary..."):
                                    transcript = get_asset(subject, chapter, video_name, 'transcription')
                                    if transcript:
                                        summary = generate_summary(transcript)
                                        save_asset(subject, chapter, video_name, 'summary', summary)
                                        pdf_buffer = generate_pdf(subject, chapter, video_name, summary)
                                        save_pdf_asset(subject, chapter, video_name, pdf_buffer)
                                        st.success("Summary generated and saved successfully!")
                                        st.rerun()
                                    else:
                                        st.error("Transcript not found. Please generate the transcript first.")

                        with col3:
                            if st.button("Generate Flashcards"):
                                with st.spinner("Generating flashcards..."):
                                    transcript = get_asset(subject, chapter, video_name, 'transcription')
                                    if transcript:
                                        flashcards = generate_flashcards(transcript)
                                        save_asset(subject, chapter, video_name, 'flashcards', flashcards)
                                        st.success("Flashcards generated and saved successfully!")
                                        st.rerun()
                                    else:
                                        st.error("Transcript not found. Please generate the transcript first.")

                        with col4:
                            if st.button("Generate Assignments"):
                                with st.spinner("Generating assignments..."):
                                    transcript = get_asset(subject, chapter, video_name, 'transcription')
                                    if transcript:
                                        assignments = extract_assignments(transcript)
                                        save_asset(subject, chapter, video_name, 'assignments', assignments)
                                        pdf_buffer = generate_pdf(subject, chapter, video_name, assignments)
                                        save_pdf_asset(subject, chapter, video_name, pdf_buffer)
                                        st.success("Assignments generated and saved successfully!")
                                        st.rerun()
                                    else:
                                        st.error("Transcript not found. Please generate the transcript first.")
                else:
                    st.info("No videos available for this subject and chapter.")

            elif action == "Upload New Video":
                st.subheader("Upload New Video")
                uploaded_file = st.file_uploader("Choose a video file", type=['mp4', 'avi', 'mov'], key="LA Video uploader")
                if uploaded_file is not None:
                    folder_path = f"{subject}/{chapter}/DeliveredLectures"
                    ensure_folder_exists(MEDIA_BUCKET_NAME, folder_path)
                    video_key = f"{folder_path}/{uploaded_file.name}"
                    s3.upload_fileobj(uploaded_file, MEDIA_BUCKET_NAME, video_key)
                    st.success(f"Video '{uploaded_file.name}' uploaded successfully!")
                    st.rerun()
