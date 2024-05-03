from flask import Flask, request, jsonify
import extract
from pymongo import MongoClient
import re
from flask_cors import CORS
import os
import logging
from bson import json_util


app = Flask(__name__)
CORS(app, origins='http://localhost:4200', supports_credentials=True)
app.config['JSON_AS_ASCII'] = False
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

connection_string = "mongodb://localhost:27017/"
database_name = "library-next-api"
collection_name = "EmployeeRepport"

@app.route('/generate-report', methods=['POST'])
def generate_report_api():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    REPORTS_FOLDER = os.path.join(BASE_DIR, 'Reports')

    auth_token = request.cookies.get('token')
    if auth_token:
        try:
            data = request.get_json()
            employee_name = data.get('employee_name')
            date = data.get('date')
            comments = data.get('comments')
            client_name = data.get('client')
            Email = data.get('employee_Email')

            if employee_name and client_name and date and comments:
                file_name = extract.generate_report(employee_name,Email,client_name, date, comments)
                file_path = os.path.join(REPORTS_FOLDER, file_name)  # Chemin complet du fichier
                extracted_text = extract.extract_pdf_content(file_path)
                date_pattern = re.compile(r"Date \: (\d{4}-\d{2}-\d{2})")
                name_pattern = re.compile(r"Rapport sur l'employé \: (.*)")
                Email_pattern = re.compile(r"Email de l'employé \: (.*)")
                client_pattern = re.compile(r"De la part de \: (.*)")
                content_pattern = re.compile(r"Commentaires \:([\s\S]*?)(?=Reconnaissance)")
                probabilities = extract.predict_sentiment(extracted_text)
                negative_sentiment, positive_sentiment = probabilities

                dates = ''
                names = ''
                contents = ''
                clients = ''
                Emails = ''

                for section in extracted_text.split("\n\n"):
                    date_match = date_pattern.search(section)
                    name_match = name_pattern.search(section)
                    email_match = Email_pattern.search(section)
                    client_match = client_pattern.search(section)
                    content_match = content_pattern.search(section)

                    if date_match:
                        dates = date_match.group(1)
                    if name_match:
                        names = name_match.group(1)
                    if email_match:
                        Emails = email_match.group(1)
                    if client_match:
                        clients = client_match.group(1)
                    if content_match:
                        contents = content_match.group(1)
                positive_sentiment_percentage = round(positive_sentiment * 100, 2)
                negative_sentiment_percentage = round(negative_sentiment * 100, 2)

                data = {
                    'Date': dates,
                    'EmployeeName': names,
                    'EmployeeEmail': Emails,
                    'ClientName': clients,
                    'FileName': file_name,
                    'PositiveSentiment': positive_sentiment_percentage,
                    'NegativeSentiment': negative_sentiment_percentage
                }

                client = MongoClient(connection_string)
                db = client[database_name]
                collection = db[collection_name]

                result = collection.insert_one(data)
                client.close()

                return jsonify({'message': 'Report generated and data saved successfully.'}), 200
            else:
                return jsonify({'error': 'Invalid request data. Please provide employee_name, client, date, and comments.'}), 400
        except Exception as e:
            logging.exception("Une erreur s'est produite lors de la génération du rapport : %s", e)
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Unauthorized'}), 401

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_FOLDER = os.path.join(BASE_DIR, 'Reports')

@app.route('/download-report', methods=['GET'])
def handle_download():
    filename = request.args.get('filename')
    if filename:
        return extract.download_file(filename)
    else:
        return jsonify({'error': 'Filename missing in JSON request'}), 400
    
@app.route('/get-all-reports', methods=['GET'])
def get_all_reports():
    try:
        # Connexion à la base de données MongoDB
        client = MongoClient(connection_string)
        db = client[database_name]
        collection = db[collection_name]

        # Récupérer tous les documents dans la collection
        all_reports = list(collection.find())

        # Convertir les ObjectId en chaînes de caractères
        for report in all_reports:
            report['_id'] = str(report['_id'])

        # Fermer la connexion à la base de données
        client.close()

        # Retourner les rapports au format JSON
        return json_util.dumps(all_reports), 200
    except Exception as e:
        logging.exception("Une erreur s'est produite lors de la récupération de tous les rapports : %s", e)
        return jsonify({'error': 'An error occurred while fetching all reports.'}), 500
if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
