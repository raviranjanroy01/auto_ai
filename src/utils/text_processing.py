"""
Text Processing Utilities

Common text cleaning, tokenization, and preprocessing
functions used across the project.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean and normalize text for processing.

    - Converts to lowercase
    - Removes extra whitespace
    - Strips leading/trailing whitespace

    Args:
        text: Raw input text.

    Returns:
        Cleaned text string.
    """
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def tokenize(text: str) -> list:
    """
    Split text into word tokens.

    Args:
        text: The text to tokenize.

    Returns:
        List of word tokens.
    """
    cleaned = clean_text(text)
    # Split on whitespace and filter empty strings
    return [token for token in cleaned.split() if token]


def remove_punctuation(text: str) -> str:
    """
    Remove punctuation from text, keeping only alphanumeric and spaces.

    Args:
        text: Input text.

    Returns:
        Text with punctuation removed.
    """
    return re.sub(r'[^\w\s]', '', text)


def split_into_sentences(text: str) -> list:
    """
    Split text into sentences.

    Args:
        text: Input text.

    Returns:
        List of sentence strings.
    """
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]
