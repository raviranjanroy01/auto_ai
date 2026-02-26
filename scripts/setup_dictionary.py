import nltk
import os

def download_dictionary():
    print("Downloading NLTK words corpus...")
    nltk.download('words')
    
    from nltk.corpus import words
    word_list = words.words()
    
    # Filter for common English words (optional, but 'words' is quite comprehensive)
    # We'll just take the whole list for now.
    
    os.makedirs('data/dictionaries', exist_ok=True)
    dict_path = 'data/dictionaries/english.txt'
    
    print(f"Saving {len(word_list)} words to {dict_path}...")
    with open(dict_path, 'w', encoding='utf-8') as f:
        for word in word_list:
            f.write(word.lower() + '\n')
    
    print("Dictionary setup complete!")

if __name__ == "__main__":
    download_dictionary()
