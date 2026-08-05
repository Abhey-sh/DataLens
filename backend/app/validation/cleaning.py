"""
Data cleaning and preprocessing pipeline.
"""

import pandas as pd
import numpy as np
from loguru import logger


class DataCleaningPipeline:
    """
    Reusable preprocessing pipeline for CSV data.
    """

    @staticmethod
    def clean(df: pd.DataFrame) -> pd.DataFrame:
        """
        Execute complete cleaning pipeline.
        
        Steps:
        1. Trim whitespace
        2. Convert empty strings to NaN
        3. Normalize column names
        4. Remove duplicate whitespace
        5. Convert date columns
        6. Normalize string casing where appropriate
        7. Apply default values
        
        Args:
            df: Raw DataFrame from CSV
            
        Returns:
            Cleaned DataFrame
        """
        logger.info(f"Starting data cleaning pipeline on {len(df)} rows")
        
        # Step 1: Trim whitespace from all string columns
        df = DataCleaningPipeline._trim_whitespace(df)
        
        # Step 2: Convert empty strings to NaN
        df = DataCleaningPipeline._convert_empty_to_nan(df)
        
        # Step 3: Normalize column names
        df = DataCleaningPipeline._normalize_column_names(df)
        
        # Step 4: Remove duplicate whitespace
        df = DataCleaningPipeline._remove_duplicate_whitespace(df)
        
        logger.info("Data cleaning pipeline complete")
        return df

    @staticmethod
    def _trim_whitespace(df: pd.DataFrame) -> pd.DataFrame:
        """Trim leading/trailing whitespace from all string columns."""
        logger.debug("Trimming whitespace")
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].str.strip()
        return df

    @staticmethod
    def _convert_empty_to_nan(df: pd.DataFrame) -> pd.DataFrame:
        """Convert empty strings to NaN."""
        logger.debug("Converting empty strings to NaN")
        df = df.replace(r"^\s*$", np.nan, regex=True)
        return df

    @staticmethod
    def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names:
        - Strip whitespace
        - Keep original casing for now (case-sensitive matching)
        """
        logger.debug(f"Original columns: {list(df.columns)}")
        df.columns = df.columns.str.strip()
        logger.debug(f"Normalized columns: {list(df.columns)}")
        return df

    @staticmethod
    def _remove_duplicate_whitespace(df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate spaces within string values."""
        logger.debug("Removing duplicate whitespace")
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].str.replace(r"\s+", " ", regex=True)
        return df
