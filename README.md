# AI_for_Lecture - Use Case5
To guide the users on how to setup AI for Lecture - Use Case 5 on their AWS Account
# Read These Steps:
 1- To setup this solution, you need to provision some resources first
 
 2-The setup currently runs on an EC2, but you can easily convert it into a container format
 
 3- reach out to myself walid.ahmed.shehata@gmail.com for any further clarifications
 
# Prerequisites:
Please make sure that your AWS account has the following resources available:

1- Amazon Bedrock Claude 3 Sonnet has been enabled in your Target AWS Region

2- IAM User, with Key pair (Access Key/Secret Access Key) that has permissions to access Amazon Bedrock and Amazon S3

3- Create an S3 Bucket to serve as a store for all Syllabus/Reference Materials that will be uploaded by the teacher. This S3 Bucket will act as a Data Source for the RAG architecture. [Will refer to it in this document as Bucket1]

4- Create in Amazon Bedrock a KnowledgeBase using Open Search Serverless as the Vector Store, use Default Chunking, use Claude 3 Haiku v1 (Bedrock model parsing) for the embeddings for multimodality

5- Create another S3 Bucket that will store all of the generated output from the App (Summaries, Videos, Presentations) [Will refer to it in this document as Bucket2]

# EC2 Preparation:

1- launch a new EC2 instance using Amazon Linux AMI

2- Connect to your EC2 terminal

3- Update YUM installer

sudo yum update -y

4- Under /home/ec2-user create a project directory

mkdir /home/ec2-user/project_folder

5- Download all files on your computer from this repo, then copy all project files to the project directory on Amazon EC2

scp -i your-key.pem -r /path/to/your/local/folder ec2-user@your-ec2-public-ip:/home/ec2-user/project_folder

6- On your EC2 instance, make sure you define the following environment variables:

* Edit the ~/.bashrc file:
* Add your environment variables at the end of the file

AWS_ACCESS_KEY_ID=........

AWS_SECRET_ACCESS_KEY=........

AWS_REGION=........

S3_BUCKET_NAME=........

S3_ARTIFACTS_BUCKET_NAME=........

BEDROCK_KNOWLEDGE_BASE_ID=........

BEDROCK_DATA_SOURCE_ID=........

* Save and exit, then run:
* run the following command: "source ~/.bashrc"

7- On Amazon Ec-2, install python 3.12

pip install python3.12

8- Navigate to the project folder

cd /home/ec2-user/project_folder

9- Create a venv

python3.12 -m venv venv

10- Activate the venv

source venv/bin/activate

11- Install the prerequisite python packages

pip install -r requirements.txt

12- Start the streamlit app

streamlit run main.py --server.port 8080(choose port)

13- Make sure in the security group of the EC2 istance that this port is enabled on the Inbound

14- Connect to the server IP:Port 

Enjoy using the app





