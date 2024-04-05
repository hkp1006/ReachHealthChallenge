import urllib.request
import json
import os
import boto3
from botocore.exceptions import ClientError
import time
import csv
from io import StringIO
from datetime import datetime, timedelta
from datetime import datetime as dt

moment = dt.now()
datefolder = "{}{}{}{}{}{}".format(moment.day, moment.month, moment.year,moment.hour, \
    moment.minute, moment.second)

REGION_NAME_CONST = 'eu-west-1'
DATABASE_NAME_CONST = 'default'
table_name = 'covid_daily_data'

def _get_aws_client(resource, region_name):
    #Generic function to create boto3 resource clients.
    try:
        return boto3.client(resource, region_name)
    except:
        raise

def _create_table(region_name, database_name, table_name, bucket_name):
    try:
        #number of retries
        retry_count = 10
        s3_bucket = f"s3://{bucket_name}"

        query = f"""create external table if not exists {table_name.lower()} \
        (date string, states bigint, total_cases bigint, testing_cases bigint, hospitalized_cases bigint,\
        in_icu_cases bigint, on_ventilator_cases bigint, death_cases bigint ) row format delimited fields terminated by ',' \
        lines terminated by '\n' stored as inputformat 'org.apache.hadoop.mapred.TextInputFormat'\
        outputformat 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'\
        location 's3://{bucket_name}/covid_daily//'\
        tblproperties ("skip.header.line.count"="1")"""
        # athena client
        client = _get_aws_client('athena', region_name)
        print("query : ", query)
        # Execution
        response = client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                'Database': database_name
            },
            ResultConfiguration={
                'OutputLocation': s3_bucket,
            }
        )
        # get query execution id
        query_execution_id = response['QueryExecutionId']

        # get execution status
        for i in range(1, 1 + retry_count):
            # get query execution
            try:
                query_status = client.get_query_execution(QueryExecutionId=query_execution_id)
                print("query_status : ", query_status)
            except Exception as exception_obj:
                raise exception_obj
            query_execution_status = query_status['QueryExecution']['Status']['State']
            if query_execution_status == 'SUCCEEDED':
                print("STATUS:" + query_execution_status)
                break

            if query_execution_status == 'FAILED':
                print("FAILED status reason : " + \
                query_status['QueryExecution']['Status']['StateChangeReason'])
                raise Exception("STATUS:" + query_execution_status)
            else:
                print("STATUS:" + query_execution_status)
                time.sleep(i)
        else:
            client.stop_query_execution(QueryExecutionId=query_execution_id)
            raise Exception('TIME OVER')
    except:
        raise

def lambda_handler(event, context):
    # TODO implement
    try:
        if os.environ['region_name']:
            region_name = os.environ['region_name']
    except KeyError:
        region_name = REGION_NAME_CONST

    try:
        if os.environ['bucketname']:
            bucket_name = os.environ['bucketname']
    except KeyError:
        raise KeyError("Bucket name not provided.")

    try:
        if os.environ['databasename']:
            database_name = os.environ['databasename']
        else:
            database_name = DATABASE_NAME_CONST
    except KeyError:
        database_name = DATABASE_NAME_CONST
        
    url = "https://api.covidtracking.com/v2/us/daily/2021-03-02/simple.json"

    with urllib.request.urlopen(url) as response:
        body_json = response.read()

    body_dict = json.loads(body_json)
    print(body_dict)
    date = body_dict['data']['date']
    states = body_dict['data']['states']
    total_cases = body_dict['data']['cases']['total']
    testing_cases = body_dict['data']['testing']['total']
    hospitalized_cases = body_dict['data']['outcomes']['hospitalized']['currently']
    in_icu_cases = body_dict['data']['outcomes']['hospitalized']['in_icu']['currently']
    on_ventilator_cases = body_dict['data']['outcomes']['hospitalized']['on_ventilator']['currently']
    death_cases = body_dict['data']['outcomes']['death']['total']
    
    _create_table(region_name, database_name, table_name, bucket_name)
    headers = ['date', 'states', 'total_cases','testing_cases','hospitalized_cases','in_icu_cases','on_ventilator_cases','on_ventilator_cases','death_cases']
    values = [[date,states,total_cases,testing_cases,hospitalized_cases,in_icu_cases,on_ventilator_cases,death_cases]]
    
    csv_buffer = StringIO()
    csv_writer = csv.writer(csv_buffer)
    csv_writer.writerow(headers)
    csv_writer.writerows(values)
    
    start_date = datefolder
    data_key = 'covid_daily/'+ start_date+'.csv'
    print(data_key)
    s3_client = _get_aws_client('s3', region_name)
    s3_client.put_object(Bucket=bucket_name, Key=data_key, Body=csv_buffer.getvalue())
    
    print(date,states,total_cases,testing_cases,hospitalized_cases,in_icu_cases,on_ventilator_cases,death_cases)
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
