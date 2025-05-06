import pandas as pd
import os
import numpy as np

def read_file(file_path):
    """
    Reads a CSV file and returns a DataFrame with specific columns.

    Args:
        file_path (str): The path to the CSV file.

    Returns:
        pd.DataFrame: A DataFrame containing the specified columns.
    """

    # Check if the file exists
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")

    # Read the CSV file
    df = pd.read_csv(file_path)

    # Select specific columns
    selected_columns = ['id', 'name', 'age']

    # Check if the selected columns exist in the DataFrame
    missing_columns = [col for col in selected_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"The following columns are missing from the DataFrame: {missing_columns}")

    # Return the DataFrame with selected columns
    return df[selected_columns]

