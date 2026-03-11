import os
import sys
import nltk
from collections import Counter

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

def download_dictionary():
    print("--- Downloading NLTK corpora (words, brown, punkt) ---")
    nltk.download('words')
    nltk.download('brown')
    nltk.download('punkt')
    nltk.download('punkt_tab')
    
    # 1. Get the list of all valid English words
    from nltk.corpus import words
    valid_words = set(w.lower() for w in words.words())
    
    # 2. Get frequency data from the Brown corpus
    print("--- Calculating word frequencies from Brown corpus ---")
    from nltk.corpus import brown
    brown_words = [w.lower() for w in brown.words() if w.lower() in valid_words]
    frequencies = Counter(brown_words)
    
    # 3. Add common shortcuts/project words
    print("--- Boosting common words and project keywords ---")
    project_words = {
        'autoai': 5000,
        'ai': 4000,
        'python': 3000,
        'r': 2000,
        'u': 2000,
        'ok': 1500,
        'idk': 1000,
        'hello': 5000
    }
    
    # 4. Combine: ensure every valid word has at least frequency 1
    # but brown words have their real frequency
    final_dict = {}
    for word in valid_words:
        final_dict[word] = frequencies.get(word, 1)
        
    for word, freq in project_words.items():
        final_dict[word] = final_dict.get(word, 0) + freq

    # 5. Save with frequencies
    os.makedirs('data/dictionaries', exist_ok=True)
    dict_path = 'data/dictionaries/english.txt'
    
    print(f"--- Saving {len(final_dict)} words with frequency data to {dict_path} ---")
    with open(dict_path, 'w', encoding='utf-8') as f:
        for word, freq in sorted(final_dict.items(), key=lambda x: x[1], reverse=True):
            f.write(f"{word} {freq}\n")
    
    # 6. Pre-train an N-Gram model for Contextual Intelligence
    print("--- Pre-training N-Gram model (This makes it smart like G-Board) ---")
    from prediction.ngram import NGramModel
    model = NGramModel(n=3)
    
    # Use a large portion of the Brown corpus for training
    sentences = brown.sents()
    count = 0
    for sent in sentences:
        model.train(" ".join(sent))
        count += 1
        if count % 5000 == 0: print(f"   Processed {count} sentences...")

    # Save the trained model
    import pickle
    model_path = 'data/models/world_model.pkl'
    os.makedirs('data/models', exist_ok=True)
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"--- World model saved to {model_path} ---")
    print("--- Dictionary and Brain upgrade complete! ---")

if __name__ == "__main__":
    download_dictionary()
