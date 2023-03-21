import csv
import io
import os
import platform
import random
import shutil
import string
import subprocess
import sys
from datetime import datetime
from glob import glob
from pathlib import Path
from threading import Thread
from time import sleep, time
from zipfile import ZipFile

import requests
import requests.auth
import wget
from lxml import html, etree
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait


# Global Variables
start_time = time()

s3_bucket_path = 's3://mh-crawling-artifacts/adeel'

local_storage_path = 'C:/ProjectsSharedData'
resources_path = f'{local_storage_path}/Resources'

chrome_executable_filename = '/chromedriver.exe'
chrome_driver_downloads_url = 'https://chromedriver.chromium.org/downloads'

# General Configurations
requests.packages.urllib3.disable_warnings()


# Utility Functions


def get_writer(file_name, _mode='w', _encoding='utf-8'):
    """This function returns an object of the file in the specified mode.

    Args:
        file_name (str): The name of the file
        _mode (char): The mode in which you want to open the file, writing is the default mode
        _encoding (str): The file encoding, default value is UTF-8

    Raises:
        FileNotFoundError: If filename is not valid
        ValueError: If mode is not valid
        LookupError: If encoding is not correct

    Returns:
        File (object): The object of the file to write
    """
    return io.open(file_name, mode=_mode, encoding=_encoding)


def get_csv_writer(file_name, _mode='w', _encoding='utf-8', _delimiter=','):
    """This function returns an object of the CSV file in the specified mode.

        Args:
            file_name (str): The name of the file
            _mode (char): The mode in which you want to open the file, writing is the default mode
            _encoding (str): The file encoding, default value is UTF-8
            _delimiter (char): Default is comma in most of the cases, rarely a pipe symbol |

        Raises:
            FileNotFoundError: If filename is not valid
            ValueError: If mode is not valid
            LookupError: If encoding is not correct

        Returns:
            File (object): The object of the CSV file to write
    """
    writer = csv.writer(open(file_name, mode=_mode, encoding=_encoding, errors='ignore'),
                        delimiter=_delimiter,
                        lineterminator='\n')

    return writer


def read_csv_as_list(file_name):
    items = []

    reader = csv.reader(open(file_name, 'r', errors='ignore', encoding='utf-8'), delimiter=',',
                        lineterminator='\n')
    header = next(reader)

    for row in reader:
        items.append(row)

    return items, header


def read_csv_as_dict(file_name, key_index=0, value_index=999):
    items = {}

    reader = csv.reader(open(file_name, 'r', errors='ignore', encoding='utf-8'), delimiter=',',
                        lineterminator='\n')
    header = next(reader)

    for row in reader:
        card_id = row[key_index]

        if value_index == 999:
            items[card_id] = row
        elif row[value_index]:
            items[card_id] = row[value_index]

    try:
        items['']
    except KeyError:
        pass

    return items, header


def read_file_as_tree(file_path):

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except UnicodeDecodeError:
            print(f'UnicodeDecodeError: File "{file_path}" is causing issues.')
            return False

        try:
            return html.fromstring(content)
        except etree.ParserError:
            print(f'Parser Error: File "{file_path}" is empty.')
            return False
    else:
        return False


def create_dir_for_storage(project_name, dir_name):
    dir_path = f'{resources_path}/{project_name}/{dir_name}'
    create_files_dir(dir_path)

    print(f'Storage Dir Path: {dir_path}')
    return dir_path


def write_to_console(text):
    """This function writes provided text on the same line of the console, kind of progress bar.

        Args:
            text (str): The text that you want to display on the console.
    """
    sys.stdout.write(f'\r{text}')
    sys.stdout.flush()


def time_progress():
    """This function calculates the running time of the script.

        Returns:
            Time (str): It returns the calculated time in a formatted way to display on console.
    """
    end = time()
    hours, rem = divmod(end - start_time, 3600)
    minutes, seconds = divmod(rem, 60)

    return '{:0>2}:{:0>2}:{:05.2f}'.format(int(hours), int(minutes), seconds)


def to_camel_case(plain_str):
    """This function returns the provided string in camel case by keeping first letter in small
        and then every other word starting with a Capital letter.

    Args:
        plain_str (str): The provided string that needs to be converted in to camel case

    Returns:
        camel_str (str): The string in the camel case
    """
    components = plain_str.split(' ')
    return components[0].lower() + ''.join(x.title() for x in components[1:])


def get_random_string(length, only_digits=False):
    """This function creates a random string of the provided length.

    Args:
        length (int): The length of the required string
        only_digits (bool): When its value is True, it only produces string of random numbers
                            When its value is False, it produces string of random alphanumerics

    Returns:
        random_str (str): The randomly generated string
    """

    if only_digits:
        letters = string.digits
    else:
        letters = string.ascii_letters

    result_str = ''.join(random.choice(letters) for i in range(length))

    return result_str


def get_tag_text(tree, xpath, _separator=''):
    """This function extracts all the text from a tree like structured element.

    Args:
        tree (elem): A tree like structure
        xpath (str): The xpath of the element that needs to be extracted
        _separator (str): The char or string that will separate multiple elements

    Returns:
        plain_text (str): The plain readable text
    """
    content = ''

    results = tree.xpath(xpath)

    for result in results:
        content += str(result).strip()

        if _separator:
            content += _separator
        else:
            return content.replace('\\n', ' ').replace('  ', ' ').strip()

    if _separator and _separator in content:
        content = content[0:-len(_separator)]

    return content.replace('\\n', ' ').replace('  ', ' ').strip()


def cleanup_text(text):
    """This function removes any extra line spaces and characters from the provided text.

    Args:
        text (str): The plain text that needs to be cleaned

    Returns:
        new_text (str): The cleaned text
    """
    new_text = text

    while True:

        if '\r' in new_text:
            new_text = new_text.replace('\r', '').strip()

        if '\n' in new_text:
            new_text = new_text.replace('\n', ' ').strip()

        if '  ' in new_text:
            new_text = new_text.replace('  ', ' ').strip()

        if '\n' not in new_text and '  ' not in new_text:
            return new_text


def save_file_locally(file_path, content, _mode='wb'):
    """This function stores the provided content in a local file.

    Args:
        file_path (str): The relative path of the file where it needs to be stored
        content: The contents of the file
        _mode (str): The mode of the file in which to write the file.
    """

    with open(file_path, mode=_mode) as f:
        f.write(content)
        f.close()


def create_files_dir(files_dir):
    """This function makes sure that the provided file path exists.

    Args:
        files_dir (str): The relative path of the directory that needs to be created recursively.

    Raises:
        FileExistsError: If the provided file path already exists.
    """

    if not os.path.isdir(files_dir):

        try:
            os.makedirs(files_dir)
        except FileExistsError:
            pass


def remove_dir_if_empty(dir_name):
    """This function makes sure that the provided file path is removed from the file storage.

    Args:
        dir_name (str): The relative path of the directory that needs to be removed.

    Raises:
        FileNotFoundError: If the file count is zero in the provided file path.

    Returns:
        Status (bool): True if file path does not exist on the file storage, Otherwise False
    """

    if os.path.isdir(dir_name):
        try:
            dirs = os.listdir(dir_name)
        except FileNotFoundError:
            dirs = []

        if len(dirs) == 0:
            os.rmdir(dir_name)
            return True
        else:
            return False

    return True


# Below are the Functions related to the AWS files uploading.


def upload_files_to_s3_bucket(project_name, aws_filename, dest_dir):
    """This function uploads the files from destination folder to remote folder on the AWS S3 bucket.

    Args:
        project_name (str): The name of the project that represents remote directory on the AWS S3 bucket.
        aws_filename (str): The relative path to the CSV file containing logs of uploaded files on to the AWS S3 bucket.
        dest_dir (str): The relative path of the local directory where files are stored temporarily for uploading.
    """

    s3_project_path = f'{s3_bucket_path}/{project_name}/'
    command = ['aws', 's3', 'cp', dest_dir, s3_project_path, '--recursive']

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    aws_writer = get_csv_writer(aws_filename, 'a')

    for line in str(result.stdout).split('\n'):

        if 'upload:' in line:
            local_path = line.split(' to ')[0].replace('upload: ', '').strip()

            s3_path = line.split(' to ')[-1].replace(s3_bucket_path, '').strip()
            file_size = str(os.path.getsize(local_path))
            time_stamp = datetime.now()

            aws_writer.writerow([s3_path, file_size, time_stamp])

    get_csv_writer(aws_filename, 'a')

    # Remove the temporary directory holding all the files after uploading to the AWS S3 bucket.
    shutil.rmtree(dest_dir, ignore_errors=True)


def wait_while_files_are_uploading(dest_dir):

    # Make sure that files of previous batch were uploaded before starting to upload a new batch.
    while not remove_dir_if_empty(dest_dir):
        write_to_console('Uploading the files to AWS...')
        sleep(0.5)


def upload_files_to_aws(project_name, aws_filename, src_dir, dest_dir):
    """This function runs a thread to start uploading the files to AWS S3 bucket.

    Args:
        project_name (str): The name of the project that represents remote directory on the AWS S3 bucket.
        aws_filename (str): The relative path to the CSV file containing logs of uploaded files on to the AWS S3 bucket.
        src_dir (str): The relative path of the local directory where files are being downloaded.
        dest_dir (str): The relative path of the local directory where files are stored temporarily for uploading.
    """

    wait_while_files_are_uploading(dest_dir)

    os.replace(src_dir, dest_dir)
    os.mkdir(src_dir)

    t = Thread(target=upload_files_to_s3_bucket, args=(project_name, aws_filename, dest_dir,))
    t.daemon = True
    t.start()


def get_urls_of_files_to_upload(records_filename, key_index, value_index):
    """This function reads the records CSV file to grab URLs of the files that needs to be uploaded on AWS S3 bucket.

    Args:
        records_filename (str): The relative path to the records CSV file that holds URLs of the files to be downloaded.
        key_index (int): The index of the column that points to the Unique Identifier Column in the records CSV.
        value_index (int): The index of the column that points to the URLs of the files in the records CSV.

    Returns:
        items (dict): A dictionary holding CARD_IDs as keys and URLs of the files as values.
    """
    items = {}

    reader = csv.reader(open(records_filename, 'r', errors='ignore', encoding='utf-8'),
                        delimiter=',',
                        lineterminator='\n')
    next(reader)  # Skip header row

    for line in reader:

        if line:
            card_id = line[key_index].lower().strip()
            file_url = line[value_index].strip()

            if file_url:
                items[card_id] = line

    print(f'Total Files to Upload: {len(items)}')
    return items


def skip_already_uploaded_files(items, aws_filename):
    """This function removes the CARD_IDs of the already uploaded files from the provided dictionary.

    Args:
        items (dict): A dictionary holding CARD_IDs as keys and URLs of the files as values.
        aws_filename (str): The relative path to the CSV file containing logs of uploaded files on to the AWS S3 bucket.

    Raises:
        KeyError: If the CARD_ID is not present in the dictionary.
    """
    counter = 0
    uploaded = 0

    if os.path.exists(aws_filename):
        uploaded_files = open(aws_filename, 'r').read().split('\n')

        for row in uploaded_files[1:]:

            if not row:
                continue

            cols = row.split(',')

            file_key = Path(cols[0]).stem

            counter += 1

            try:
                del items[file_key]
                uploaded += 1
            except KeyError:
                continue

    print(f'Uploaded Files: {uploaded}/{counter} | Remaining: {len(items)}')


def traverse_files(items, src_dir):
    count = 0
    download_count = 0

    for _file in glob(src_dir+'/*'):

        if not _file:
            continue

        file_key = Path(_file).stem

        count += 1

        try:
            del items[file_key]
            download_count += 1
        except KeyError:
            continue

    return count, download_count


def skip_already_downloaded_files(items, src_dir):
    """This function removes the CARD_IDs of the already uploaded files from the provided dictionary.

    Args:
        items (dict): A dictionary holding CARD_IDs as keys and URLs of the files as values.
        src_dir (str): The relative path of the local directory where files are being downloaded.

    Raises:
        KeyError: If the CARD_ID is not present in the dictionary.
    """
    counter = 0
    downloaded = 0

    files = glob(src_dir+'/*.jpg')

    if files:
        count, download_count = traverse_files(items, src_dir)

        counter += count
        downloaded += download_count
    else:
        dirs = glob(src_dir+'/*')

        if dirs:

            for _dir in dirs:
                files = glob(_dir + '/*.jpg')

                if files:
                    count, download_count = traverse_files(items, _dir)

                    counter += count
                    downloaded += download_count

    print(f'Downloaded Files: {downloaded}/{counter} | Remaining: {len(items)}')


def get_urls_to_upload_after_configurations(records_filename, aws_filename, src_dir, key_index, value_index):
    """This function prepares the Environment for files uploading and specify remaining files that are not uploaded yet.

    Args:
        records_filename (str): The relative path to the records CSV file that holds URLs of the files to be downloaded.
        aws_filename (str): The relative path to the CSV file containing logs of uploaded files on to the AWS S3 bucket.
        src_dir (str): The relative path of the local directory where files are being downloaded.
        key_index (int): The index of the column that points to the Unique Identifier Column in the records CSV.
        value_index (int): The index of the column that points to the URLs of the files in the records CSV.

    Returns:
        items (dict): A dictionary holding CARD_IDs as keys and URLs of the files as values.
    """
    if not os.path.isdir(src_dir):
        os.mkdir(src_dir)

    if not os.path.exists(aws_filename):
        aws_writer = get_csv_writer(aws_filename)
        aws_writer.writerow(['S3 Path', 'File Size', 'Timestamp'])

    get_csv_writer(aws_filename, 'a')

    items = get_urls_of_files_to_upload(records_filename, key_index=key_index, value_index=value_index)

    skip_already_uploaded_files(items, aws_filename)
    skip_already_downloaded_files(items, src_dir)

    return items


# Below are the Functions related to the Backend that use Requests module.


def get_tree(page_url, retries=2, _verify=True, _timeout=15):

    while True:

        try:
            response = requests.get(page_url, verify=_verify, timeout=_timeout)

            if response.status_code == 200:
                return html.fromstring(response.content)
            elif response.status_code == 404:
                return False
            else:
                raise Exception

        except Exception as e:

            if '[Errno 11001] getaddrinfo failed' in str(e):
                write_to_console('Internet Connection Error! Retrying...')
            else:
                retries -= 1

            if retries == 0:
                return False

            sleep(0.5)


def get_page_tree(driver, _sleep=1):
    sleep(_sleep)
    return html.fromstring(driver.page_source)


def get_file(file_url, file_path, retries=2):

    while True:

        try:
            response = requests.get(file_url, timeout=15)

            if response.status_code == 200:
                save_file_locally(file_path, response.content)
                return True
            elif response.status_code == 404:
                return False
            else:
                raise Exception

        except Exception as e:

            if '[Errno 11001] getaddrinfo failed' in str(e):
                write_to_console('Internet Connection Error! Retrying...')
            else:
                retries -= 1

            if retries == 0:
                return False

            sleep(0.5)


def get_windows_chrome_version():
    cmd = "(Get-Item (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe').'(Default)').VersionInfo"
    version_string = subprocess.run(["powershell", "-Command", cmd], capture_output=True)

    item_details = {}

    items = str(version_string.stdout)[2:-1].split('\\r\\n')

    for item in items:

        if item and item.isascii():
            cols = item.split()

            if len(cols) > 0 and cols[0].replace('-', '').strip():
                cols[2] = ' '.join(cols[2:]).replace('\\\\', '\\')

                if len(item_details) == 0:

                    for col in cols:
                        item_details[col] = []
                else:
                    index = 0

                    for key in item_details:
                        # item_details[key].append(cols[index])
                        item_details[key] = cols[index]
                        index += 1

    return item_details


def get_installed_chrome_version():
    osname = platform.system()

    if osname == 'Darwin':
        install_path = "/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome"
        version_string = ""
        return version_string

    elif osname == 'Windows':
        product_details = get_windows_chrome_version()
        return product_details["FileVersion"]
    elif osname == 'Linux':
        install_path = "/usr/bin/google-chrome"
        cmd = "google-chrome --version"
    else:
        raise NotImplemented(f"Unknown OS '{osname}'")


def download_chrome_driver_for_specific_version_of_chrome_browser(chrome_version):
    chrome_driver_filename = ''

    response = requests.get(chrome_driver_downloads_url)

    if response.status_code == 200:
        tree = html.fromstring(response.content)

        major_chrome_version = chrome_version.split('.')[0]
        chrome_version_link = get_tag_text(tree, f'.//a[contains(text(), "ChromeDriver {major_chrome_version}.")]/@href')

        if chrome_version_link:
            chrome_path = chrome_version_link.split('path=')[-1].replace('/', '').strip()
            chrome_download_link = f'https://chromedriver.storage.googleapis.com/{chrome_path}/chromedriver_win32.zip'
            chrome_driver_name = Path(chrome_download_link).name

            print('Downloading chromedriver...')
            chrome_driver_filename = wget.download(chrome_download_link, chrome_driver_name)
            print('Chromedriver downloaded successfully!')
        else:
            print(f'Unable to find Chrome Driver Version link from Chrome Downloads page: {chrome_driver_downloads_url}')
    else:
        print(f'Unable to fetch Chrome Driver Version link from Chrome Downloads link: {chrome_driver_downloads_url}')

    return chrome_driver_filename


def extract_chrome_driver_file_to_dest_dir(chrome_driver_filename, chrome_executable_path):

    chrome_executable_filepath = f'{chrome_executable_path}/{chrome_executable_filename}'

    with ZipFile(chrome_driver_filename, 'r') as _zip:
        # printing all the contents of the zip file
        _zip.printdir()

        print('Extracting all the files now...')
        _zip.extractall()

    shutil.move(chrome_executable_filename, chrome_executable_filepath)
    print(f'Placed "{chrome_executable_filename}" to {chrome_executable_filepath}.')

    os.remove(chrome_driver_filename)
    print(f'Removed {chrome_driver_filename} from current directory.')


def download_chrome_driver(download_path=''):

    if not download_path:
        download_path = local_storage_path

    chrome_version = get_installed_chrome_version()

    chrome_driver_filename = download_chrome_driver_for_specific_version_of_chrome_browser(chrome_version)

    if chrome_driver_filename:
        extract_chrome_driver_file_to_dest_dir(chrome_driver_filename, download_path)

    print('Successfully downloaded the chromedriver.')


def get_recursive_filepaths(directory):
    """
    This function will generate the file names in a directory
    tree by walking the tree either top-down or bottom-up. For each
    directory in the tree rooted at directory top (including top itself),
    it yields a 3-tuple (dirpath, dirnames, filenames).
    """
    file_paths = []

    for root, directories, files in os.walk(directory):

        for filename in files:
            filepath = os.path.join(root, filename)
            file_paths.append(filepath)

    return file_paths


def get_filepaths(directory, _extension='html', _depth=1):
    directory = directory.replace('./', '').strip('/')
    directory_depth = '/*' * _depth

    if ':/' not in directory:
        directory_path_pattern = f'./{directory}{directory_depth}.{_extension}'
    else:
        directory_path_pattern = f'{directory}{directory_depth}.{_extension}'

    filepaths = glob(directory_path_pattern)

    print(f'Fetching Files | Count: {len(filepaths)} | Dir: {directory_path_pattern}')

    return filepaths


def generate_card_ids(starting_id, ending_id):
    return {str(card_id): '' for card_id in range(starting_id, ending_id + 1)}


def remove_existing_files(card_ids, dir_pattern):
    scraped_card_ids = glob(dir_pattern)

    for file_path in scraped_card_ids:
        card_id = Path(file_path).stem

        try:
            del card_ids[card_id]
        except KeyError:
            pass


# Below are the Selenium Browser utils.


def load_driver(headless=False):
    """This function opens a Chrome browser after some configurations and returns chrome driver object.

    Args:
        headless (bool): True to run the Chrome browser in the foreground otherwise it will run in background.

    Returns:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
    """
    chrome_options = Options()

    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    if headless:
        chrome_options.add_argument("--headless")

    chrome_executable_filepath = f'{local_storage_path}/{chrome_executable_filename}'

    try:
        driver = webdriver.Chrome(options=chrome_options, executable_path=chrome_executable_filepath)
    except exceptions.WebDriverException:
        driver = webdriver.Chrome(options=chrome_options)

    return driver


# Following are the Functions to interact with multiple elements.


def wait_for_elems(driver, elems_xpath, _wait_in_secs=10):
    """This function wait until the presence of the specified elements is located on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elems_xpath (str): The xpath of the elements that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Returns:
        WebDriverElement (list): if it is found successfully, Otherwise False
    """
    try:
        return WebDriverWait(driver, _wait_in_secs).until(
                    EC.presence_of_all_elements_located((
                        By.XPATH, elems_xpath)))
    except exceptions.TimeoutException:
        return False


def wait_for_elems_by_text(driver, elem_text, _elem_index=0, _wait_in_secs=10, _sleep=0.2):
    """This function wait until the presence of the specified elements is located on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_text (str): The visible text of the element that you want to look for.
        _elem_index (int): In case of multiple elements, you can specify index of the element to interact with.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.

    Returns:
        WebDriverElement (list): if it is found successfully, Otherwise False
    """
    elems_by_having_text_xpath = f'.//*[contains(text(), "{elem_text}")]'

    elems = wait_for_elems(driver, elems_by_having_text_xpath, _wait_in_secs)

    if len(elems) > 1 and _elem_index == 0:
        elems_by_exact_text_xpath = f'.//*[text()="{elem_text}"]'

        exact_elems = wait_for_elems(driver, elems_by_exact_text_xpath)

        if len(exact_elems) == 1:
            elems = exact_elems

    if _elem_index >= len(elems):
        return False

    return elems


def locate_elems(driver, elems_xpath, _wait_in_secs=10):
    """This function wait until the specified elements becomes visible on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elems_xpath (str): The xpath of the elements that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Returns:
        WebDriverElement (list): if it is found successfully, Otherwise False
    """
    try:
        return WebDriverWait(driver, _wait_in_secs).until(
            EC.visibility_of_all_elements_located((
                By.XPATH, elems_xpath)))
    except exceptions.TimeoutException:
        return False


def locate_elems_by_text(driver, elems_text, _elem_index=0, _wait_in_secs=10):
    """This function wait until the specified elements becomes visible having specified text on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elems_text (str): The visible text of the elements that you want to look for.
        _elem_index (int): In case of multiple elements, you can specify index of the element to interact with.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Returns:
        WebDriverElement (list): if it is found successfully, Otherwise False
    """
    elems_by_having_text_xpath = f'.//*[contains(text(), "{elems_text}")]'

    elems = locate_elems(driver, elems_by_having_text_xpath, _wait_in_secs)

    if len(elems) > 1 and _elem_index == 0:
        elems_by_exact_text_xpath = f'.//*[text()="{elems_text}"]'

        exact_elems = locate_elems(driver, elems_by_exact_text_xpath, _wait_in_secs)

        if len(exact_elems) == 1:
            elems = exact_elems

    if _elem_index >= len(elems):
        return False

    return elems


# Following are the Functions to interact with single elements.


def wait_until_text_present(driver, elem_xpath, elem_text, _wait_in_secs=10):
    """This function wait until the specified element becomes visible on the Web Page and also contains specified text.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_xpath (str): The xpath of the element that you want to look for.
        elem_text (str): The visible text of the element that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Returns:
        element (WebDriverElement): if it is found successfully, Otherwise False
    """
    try:
        return WebDriverWait(driver, _wait_in_secs).until(
                    EC.text_to_be_present_in_element((
                        By.XPATH, elem_xpath), elem_text))
    except exceptions.TimeoutException:
        return False


def wait_for_elem(driver, elem_xpath, _wait_in_secs=10):
    """This function wait until the presence of the specified element is located on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_xpath (str): The xpath of the element that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Returns:
        element (WebDriverElement): if it is found successfully, Otherwise False
    """
    try:
        return WebDriverWait(driver, _wait_in_secs).until(
                    EC.presence_of_element_located((
                        By.XPATH, elem_xpath)))
    except exceptions.TimeoutException:
        return False


def locate_elem(driver, elem_xpath, _wait_in_secs=10):
    """This function wait until the specified element becomes visible on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_xpath (str): The xpath of the element that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Returns:
        element (WebDriverElement): if it is found successfully, Otherwise False
    """
    try:
        return WebDriverWait(driver, _wait_in_secs).until(
            EC.visibility_of_element_located((
                By.XPATH, elem_xpath)))
    except exceptions.TimeoutException:
        return False


def locate_elem_by_text(driver, elem_text, _elem_index=0, _wait_in_secs=10):
    """This function wait until the specified element becomes visible on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_text (str): The visible text of the element that you want to look for.
        _elem_index (int): In case of multiple elements, you can specify index of the element to interact with.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Raises:
        IndexError: If specified index does not exist in the list.

    Returns:
        element (WebDriverElement): It returns the specific element from the list.
    """
    elems = locate_elems_by_text(driver, elem_text, _elem_index=_elem_index, _wait_in_secs=10)

    return elems[_elem_index]


def clickable_elem(driver, elem_xpath, _wait_in_secs=10):
    """This function wait until the specified element becomes clickable on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_xpath (str): The xpath of the element that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.

    Returns:
        element (WebDriverElement): if it is found successfully, Otherwise False
    """
    try:
        return WebDriverWait(driver, _wait_in_secs).until(
                    EC.element_to_be_clickable((
                        By.XPATH, elem_xpath)))
    except exceptions.TimeoutException:
        return False


def click_elem(driver, elem_xpath, _wait_in_secs=10, _sleep=0.2):
    """This function clicks on the specified element after it becomes clickable on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_xpath (str): The xpath of the element that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.
    """
    elem_to_click = clickable_elem(driver, elem_xpath, _wait_in_secs)

    elem_to_click.click()

    sleep(_sleep)


def click_elem_by_text(driver, elem_text, _elem_index=0, _wait_in_secs=10, _sleep=0.2):
    """This function clicks on the element having specified text after the element is located on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_text (str): The visible text of the element that you want to look for.
        _elem_index (int): In case of multiple elements, you can specify index of the element to interact with.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.
    """
    elems = locate_elems_by_text(driver, elem_text, _wait_in_secs)

    driver.execute_script("arguments[0].click();", elems[_elem_index])

    sleep(_sleep)


def extract_elem_text(driver, elem_xpath, _wait_in_secs=5):
    elem = wait_for_elem(driver, elem_xpath, _wait_in_secs=_wait_in_secs)

    if elem:
        return str(elem.text).strip()
    else:
        return ''


def send_keys_to_elem(driver, elem_xpath, keys, _clear=True, _wait_in_secs=10, _sleep=0.2):
    """This function writes specified text in the field once that field is located on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_xpath (str): The xpath of the element that you want to look for.
        keys (str): The plain text to write in the field.
        _clear (bool): If True then clears the field before writing new text, Otherwise just append the text.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.
    """
    elem_to_send_keys_to = locate_elem(driver, elem_xpath, _wait_in_secs)

    if _clear:
        elem_to_send_keys_to.clear()

    elem_to_send_keys_to.send_keys(keys)
    sleep(_sleep)


def send_keys_to_elem_by_text(driver, elem_text, keys, _clear=True, _wait_in_secs=10, _sleep=0.2):
    """This function writes specified text in the field once that field is located having specified text on the Web Page.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_text (str): The visible text of the element that you want to look for.
        keys (str): The plain text to write in the field.
        _clear (bool): If True then clears the field before writing new text, Otherwise just append the text.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.
    """
    elem_to_send_keys_to = locate_elem_by_text(driver, elem_text, _wait_in_secs)

    if _clear:
        elem_to_send_keys_to.clear()

    elem_to_send_keys_to.send_keys(keys)

    sleep(_sleep)


# Following are the Functions to perform certain actions on the Frontend using driver.


def save_browser_page_locally(driver, file_path, _sleep=0.25):
    sleep(_sleep)
    page_content = driver.page_source

    writer = get_writer(file_path)
    writer.write(page_content)
    writer.close()


def select_dropdown_value_by_text(driver, elem_xpath, dropdown_text):
    """This function selects one of the option from the given dropdown list via visible text of the option.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_xpath (str): The xpath of the element that you want to look for.
        dropdown_text (str): The text of the one of the options from the dropdown list.
    """
    elem = locate_elem(driver, elem_xpath)
    select = Select(elem)
    select.select_by_visible_text(dropdown_text)


def wait_until_url_contains_text(driver, elem_text, _wait_in_secs=10, _sleep=0.5):
    """This function wait until the current URL does not contain the specified text.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        elem_text (str): The visible text of the element that you want to look for.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.

    Returns:
        status (bool): If the URL contains the specified text then True, Otherwise False.
    """
    try:
        WebDriverWait(driver, _wait_in_secs).until(
            EC.url_contains(elem_text))
        sleep(_sleep)
        return True
    except exceptions.TimeoutException:
        return False


def switch_to_iframe(driver, _iframe_xpath='.//iframe', _wait_in_secs=10, _sleep=0.5):
    """This function switches focus of the Chrome driver to the specified iframe.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        _iframe_xpath (str): The xpath of the iframe that you want to switch to.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.

    Returns:
        status (bool): If the focus switched to the specified iframe then True, Otherwise if iframe not exists then False.
    """
    iframe = wait_for_elem(driver, _iframe_xpath, _wait_in_secs)

    if iframe:
        driver.switch_to.frame(iframe)
        sleep(_sleep)
        return True

    return False


def switch_to_iframes_within_iframes_until_exists(driver, _wait_in_secs=5, _sleep=0.5):
    """This function wait until the current URL does not contain the specified text.

    Args:
        driver (WebDriver): The Chrome driver object to handle the Chrome browser.
        _wait_in_secs (int): WebDriver waits for specified number of seconds while looking for the element.
        _sleep (float): The time for which WebDriver waits after performing the action
                        so the page could be loaded successfully and for the smooth experience with WebDriver.

    Returns:
        status (bool): If the URL contains the specified text then True, Otherwise False.
    """
    while switch_to_iframe(driver, _wait_in_secs=_wait_in_secs, _sleep=_sleep):
        pass


def scroll_down_to_bottom_of_page(driver, _pause_in_scroll=1):
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        sleep(_pause_in_scroll)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            break

        last_height = new_height


def scroll_to_elem(driver, elem_xpath, _wait_in_secs=10, _pause_in_scroll=1):
    elem = wait_for_elem(driver, elem_xpath, _wait_in_secs=_wait_in_secs)

    if elem:
        driver.execute_script('arguments[0].scrollIntoView();', elem)

        sleep(_wait_in_secs)

        return elem
    else:
        return False
