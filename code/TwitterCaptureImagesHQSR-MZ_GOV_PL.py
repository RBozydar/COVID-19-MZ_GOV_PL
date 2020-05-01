""" 
Author: Anna Ochab-Marcinek 
ochab@ichf.edu.pl
http://groups.ichf.edu.pl/ochab

Tested on: 
Python 3.6.10 :: Anaconda, Inc.
jupyter-notebook 6.0.3

This script 

1. Gets data on COVID-19:
tested (cumulative numbers) 
in Poland
from the Twitter account of the Polish Health Ministry: https://twitter.com/MZ_GOV_PL
    a) Get the images from Twitter
    b) OCR the images to get numbers
    
2. Updates an existing local CSV data file.
Prerequisites: 
    a) The old data file must exist.
    b) The old data file name format must be the following: old_csv_file_name = path + "cor." + day_str + ".csv" 
    where day_str = date_i_days_ago.strftime("%Y.%m.%d")
    For example, the old data file is: ../cor.2020.04.07.csv
    c) The old data file should have the following column headers:
    Data,Dzień,Wykryci zakażeni,Testy,Hospitalizowani,Zmarli,Kwarantanna,Nadzór,"Testy, wartości przybliżone",Kwarantanna po powrocie do kraju,Wydarzenia,Wyzdrowiali
    d) The following is a bit inconsistent but, for historical reasons: 
        - Column names are in Polish; in particular, the date column name is 'Data'. 
        - However, dates in the date column must be in American date format:
        myfile_date_format = '%m/%d/%Y'
Output is written to: new_csv_file_name = path + "cor." + today_str + ".csv"


"""

#######################################################################################
from twitter_scraper import get_tweets
import re
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import matplotlib.dates as mdates
import glob
import requests
import sys
import os
#######################################################################################

# OCR image type 1 
# ocr_hqsr(path_filename_in_)
# returns: hospitalized, quarantined, supervised, recovered
exec(open('../code/TwitterCaptureImages_functions.py').read())
# import TwitterCaptureImages_functions # For some reason, this doesn't work in my Jupyter notebook...(?)
############################################################################################################
exec(open('../code/TwitterCaptureOther_functions.py').read())
#######################################################################################

# CSV data path
path = "../data/"

# Path to the directory for captured images
imgpath = "../twitter_images/"

# Path to the directory for captured data (CSV)
twitter_data_path = "../twitter_captured_data/"

# Error log path
err_log_path = "../ocr_errors/"

# Twitter user account
twitter_user = 'MZ_GOV_PL'

# Number of Twitter pages to read
pages_number=3

# Note that my csv file uses the American date format!
myfile_date_format = '%m/%d/%Y'

# Temporarily: Data range to display when running the script
data_range=slice(55,65,None)
# Temporarily: Max column width to display when running the script
max_column_width=20

# Strings to find in tweets
start = 'Dzienny raport o'
# middle = '/'
# # mark parentheses with backslash to avoid misinterpretation!
# end = '\(wszystkie pozytywne przypadki/w tym osoby zmarłe\)' 

# Create a dictionary of tweets
tweets = []
print_spacer()
print("Getting tweets from", twitter_user, "...")
for i in get_tweets(twitter_user, pages=pages_number):
    tweets.append(i) 
# print(repr(tweets))

# Convert tweets to pandas.DataFrame
df=pd.DataFrame.from_dict(tweets)

# Select rows in df which contain the string defined in the start variable
# and create df_hqsr (our twitter data frame)
df_hqsr=df[df['text'].str.contains(start, na=False)]


# Add a new column to the twitter data frame: 'tested' 
df_hqsr = df_hqsr.reindex(
    df_hqsr.columns.tolist() + ['hospitalized','quarantined','supervised','recovered'], axis=1) 

# Open error log file
errlogfile = open(err_log_path + 'OCR_errors.log', 'a')
# Open error correction file
errcorrectfile_name=err_log_path + 'OCR_error_correction.csv'
if not os.path.exists(errcorrectfile_name):
    errcorrectfile = open(errcorrectfile_name, 'w')
    print("\"Date\",\"Column\",\"is\",\"should be\"", file=errcorrectfile)
else:
    if os.path.getsize(errcorrectfile_name) > 0:
        # Check for newline at EOF. If it is not there, add it.
        errcorrectfile = open(errcorrectfile_name, 'r')
        # Get file as string. This will also be needed later.
        errcorrectfile_str = str(errcorrectfile.read())
        last_chr = errcorrectfile_str[-1]
        errcorrectfile.close()
        errcorrectfile = open(errcorrectfile_name, 'a')
        if not '\n' in last_chr:
            # Add newline at EOF 
            errcorrectfile.write('\n')
    else:
        errcorrectfile = open(errcorrectfile_name, 'a')
        errcorrectfile_str=""
        print("\"Date\",\"Column\",\"is\",\"should be\"", file=errcorrectfile)

ERRFLAG=0
# Download images that contain data
# Find the numbers of tested in the images.
# Write these numbers in the 'tested' column.
# df_hqsr.iterrows() returns the list: index, row
# index : a row index (a number)
# row : whole row
for index, row in df_hqsr.iterrows(): 
    # Get image url
    photo_url = row['entries'].get('photos')[0]
    # Get image time stamp
    timestamp = row['time'].strftime("%Y.%m.%d")
    # Download image
    myfile = requests.get(photo_url)
    # Write image; image name will have the time stamp.
    img_file_name = imgpath+"TCImageHqsrMZ_GOV_PL."+timestamp+".jpg"
    open(img_file_name, 'wb').write(myfile.content)
    # OCR image to get the cumulative number of tested patients
    # number_list contains: hospitalized, quarantined, supervised, recovered
    
    d1=pd.to_datetime(row['time'])
    d2=datetime(2020,4,16,9,0,34) # change of image format on this date
    if(d1>=d2): 
        numbers = ocr_hqsr(img_file_name)
    else:
        numbers = ocr_hqsr_old(img_file_name) # for old image format
    labels=['hospitalized', 'quarantined', 'supervised', 'recovered']
    # Create a dictionary from two lists
    labels_numbers = {labels[i]: numbers[i] for i in range(len(labels))} 
    
    for label in labels_numbers:
        # print(label, labels_numbers[label])
        number_str = labels_numbers[label]
        is_number = number_str.isnumeric() #all(map(str.isdigit, number_str))
        if(is_number):
        # Insert the cumulative number of tested patients the 'tested' column of df_hqsr.
            df_hqsr.loc[index,label] = int(number_str)
        else:
            ERRFLAG=1
            df_hqsr.loc[index,label] = number_str
            error_message_str = datetime.now().strftime("%Y.%m.%d %H:%M:%S")+ " OCR error! "+ label+ " : "+ number_str+ " is not a number in "+ img_file_name 
            print(error_message_str, file = errlogfile)
            print(error_message_str ,file = sys.stderr)
            new_error=df_hqsr.loc[index,'time'].strftime(myfile_date_format)+","+label+ ","+ number_str+ ","
            # Check if this error already exists in OCR error file (also if corrected)
            if not new_error in errcorrectfile_str:
                print(new_error,file = errcorrectfile)
            else:
                print("\tThis error already exists in the OCR error file "+errcorrectfile_name, file=sys.stderr)    

if ERRFLAG:
    print("\nIf not already corrected, correct these errors manually in " + err_log_path + "OCR_error_correction.csv",file = sys.stderr)
    print("and run the error correction script run_error_correction.sh",file = sys.stderr)

# Close error log file
errlogfile.close()
errcorrectfile.close()

# For some reason, the numbers entered to columns are float...    
# Convert the 'tested' column to int  
# df_hqsr = df_hqsr.astype({'hospitalized':int,'quarantined':int,'supervised':int,'recovered':int})

# Reset index (because old indexes were inherited from df) 
df_hqsr = df_hqsr.reset_index(drop=True)

# For check, write the downloaded data to a file: 
df_hqsr_to_export = df_hqsr[['time', 'hospitalized','quarantined','supervised','recovered']]
today = date.today()
today_str = today.strftime("%Y.%m.%d")

captured_data_file_name = twitter_data_path+"TChqsrMZ_GOV_PL."+today_str+".csv"
df_hqsr_to_export.to_csv (captured_data_file_name, index = False, header=True)



# Update the existing CSV data file
# 
# Automatically find the previous data file
filename = find_last_local_data_file()


# For some reason, I can't use the result of glob.glob(filename) above (why?)
# I use the filename instead
old_csv_file_name = filename
new_csv_file_name = path + "cor." + today_str + ".csv"
# Read the latest existing CSV data file
myfile_df = pd.read_csv(old_csv_file_name)

# Show part of the old csv file as a table (I need to improve this)
# Works in Jupyter notebook / IPython
# Display more columns in Ipython
pd.set_option('display.max_columns', 20)
pd.set_option('display.max_colwidth', max_column_width)
display(myfile_df[data_range])


# The newest row index is 0 in the tweets data frame df_confirmed_deaths
# Newest date in df_hqsr, read as string
newest_twitter_date_str = df_hqsr.loc[0,'time']



# Convert newest_twitter_date to myfile_date_format.
# newest_twitter_date is the date corresponding to the last record of my Twitter data.
newest_twitter_date = newest_twitter_date_str.strftime(myfile_date_format)

# This will be the row index of my csv file corresponding to the last record of my Twitter data.
# In other words, the row with newest_myfile_index will have the same date as newest_twitter_date.
# For now, we set it to 0.
newest_myfile_index = 0

# To get newest_myfile_index:
# Search for newest_twitter_date in all rows of myfile_df, in the 'Data' column
for myfile_index, row in myfile_df.iterrows():
    # For some reason, I need to re-format the 'Data' column content (...?)
    reformatted_date = pd.to_datetime(row['Data']).strftime(myfile_date_format)
    # If newest_twitter_date is found in myfile_df:
    if reformatted_date == newest_twitter_date:
        # Remember newest_myfile_index
        newest_myfile_index  = myfile_index
#         print("reformatted_date, newest_twitter_date", reformatted_date, newest_twitter_date)


# Update my file        
# We will loop through the rows of my file data and Twitter data 
# and overwrite the data in my file with the Twitter data
myfile_increment_index=0
twitter_increment_index=0

# df_hqsr.tail(1).index.item() : last index
last_twitter_index = df_hqsr.tail(1).index.item()

# Loop from the 0-th to last row in the Twitter data:
# For some reason it does not update under the last index
while twitter_increment_index<=last_twitter_index:
    # Note the difference in time ordering of my csv file data and the Twitter data:
    # newest_myfile_index-myfile_increment_index : we move up my csv file
    # 0+twitter_increment_index : we move down the Twitter data
    myfile_df.loc[newest_myfile_index-myfile_increment_index, 'Hospitalizowani'] =\
      df_hqsr.loc[twitter_increment_index,'hospitalized']
    myfile_df.loc[newest_myfile_index-myfile_increment_index, 'Kwarantanna'] =\
      df_hqsr.loc[twitter_increment_index,'quarantined']
    myfile_df.loc[newest_myfile_index-myfile_increment_index, 'Nadzór'] =\
      df_hqsr.loc[twitter_increment_index,'supervised']
    myfile_df.loc[newest_myfile_index-myfile_increment_index, 'Wyzdrowiali'] =\
      df_hqsr.loc[twitter_increment_index,'recovered']
# Zmienić to na pętlę po słowniku
     
    # Go to the previous day in my csv file: move by one row (each row is one day in that file)
    myfile_increment_index = myfile_increment_index + 1
    
    # Try to go to the previous day in Twitter data: move by one row
    twitter_increment_index = twitter_increment_index + 1
    


print_message("Captured images written to local directory:", imgpath)

print_message("Captured data written to local data file:", captured_data_file_name)

# Show the captured data
# Works in Jupyter notebook / IPython
display(df_hqsr_to_export)        


# Export the updated file to CSV
myfile_df.to_csv(new_csv_file_name, index=False)

print_message("Update written to local data file:", new_csv_file_name)


# Show part of the new csv file as a table (I need to improve this)
# Works in Jupyter notebook / IPython
display(myfile_df[data_range])