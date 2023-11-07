from airflow import DAG
from datetime import timedelta, datetime
import pandas as pd
from airflow.providers.http.sensors.http import HttpSensor
import json
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.operators.python import PythonOperator


# function to convert kelvin to degree celsius
def kelvin_to_celsius(temp):
  return round(temp - 273.15,2)

def transform_load_data(task_instance):
    data = task_instance.xcom_pull(task_ids='extract_weather_data')
    # accessing each field in the nested json and storing it in variables
    city = data["name"]
    weather_description = data['weather'][0]['description']
    temp_farenheit = kelvin_to_celsius(data['main']['temp'])
    feels_like_farenheit = kelvin_to_celsius(data['main']['feels_like'])
    min_temp_farenheit = kelvin_to_celsius(data['main']['temp_min'])
    max_temp_farenheit = kelvin_to_celsius(data['main']['temp_max'])
    pressure = data['main']['pressure']
    humidity = data['main']['humidity']
    wind_speed = data['wind']['speed']
    time_of_record = datetime.utcfromtimestamp(data['dt']+data['timezone'])
    sunrise_time = datetime.utcfromtimestamp(data['dt']+data['sys']['sunrise'])
    sunset_time = datetime.utcfromtimestamp(data['dt']+data['sys']['sunset'])
    # storing the entire data as a plain dictionary
    transformed_data = {
        'city':city,
        'weather_description':weather_description,
        'temp_farenheit':temp_farenheit,
        'feels_like_farenheit':feels_like_farenheit,
        'min_temp_farenheit':min_temp_farenheit,
        'max_temp_farenheit':max_temp_farenheit,
        'pressure':pressure,
        'humidity':humidity,
        'wind_speed':wind_speed,
        'time_of_record':time_of_record,
        'sunrise_time':sunrise_time,
        'sunset_time':sunset_time
    }

    aws_credentials = {
       "key":"*************************",
       "secret":"*******************************",
       "token":"**************************************************************************************"
    }

    # loading the dictionary into list
    transformed_data_list = [transformed_data]
    # converting the data into DataFrame
    df_data = pd.DataFrame(transformed_data_list)
    # using now function to get present timestamp, which we will use in file name
    now = datetime.now()
    # converting our present timestamp into desired string format
    dt_string = now.strftime("%Y%m%d%H%M%S")
    # specifying file name with date string
    dt_file_string = "current_weather_data" + "_" + city + "_" + dt_string
    # saving our dataframe as csv
    df_data.to_csv(f"s3://weatherdata-airflow-ec2-s3-project/{dt_file_string}.csv",index=False, storage_options=aws_credentials)


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023,1,8),
    'email': ['________________'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2)
}

# dag name should be unique from all our existing dags
with DAG('weather_dag',
        default_args=default_args,
        schedule_interval='@daily',
        catchup=False) as dag:
    
    is_weather_api_ready = HttpSensor(
        task_id='is_weather_api_ready',
        http_conn_id='weathermap_api',
        endpoint='/data/2.5/weather?q=guntur&appid=dcce08df2f68d12345c080a8270e5ca8'
    )

    extract_weather_data = SimpleHttpOperator(
        task_id='extract_weather_data',
        http_conn_id='weathermap_api',
        endpoint='/data/2.5/weather?q=guntur&appid=dcce08df2f68d12345c080a8270e5ca8',
        method='GET',
        response_filter=lambda r:json.loads(r.text),
        log_response=True
    )

    transform_load_weather_data = PythonOperator(
       task_id = 'transform_load_weather_data',
       python_callable=transform_load_data
    )

    is_weather_api_ready >> extract_weather_data >> transform_load_weather_data