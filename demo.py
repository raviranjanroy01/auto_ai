"""
AutoAI — Interactive Demo
=========================
A command-line demo showcasing:
  1. Auto-correction (typo fixing)
  2. Next-word prediction
  3. Real-time learning from your input

Run: python demo.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from autocorrect import AutoCorrector, Dictionary
from prediction import WordPredictor
from user_model import UserProfile, UserLearner


# ─── Terminal Colors ─────────────────────────────────────────────
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Background
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_MAGENTA = "\033[45m"


def colored(text, color):
    return f"{color}{text}{Colors.RESET}"


def bold(text):
    return f"{Colors.BOLD}{text}{Colors.RESET}"


# ─── Display Helpers ─────────────────────────────────────────────
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    banner = f"""
{colored('╔══════════════════════════════════════════════════════════════╗', Colors.CYAN)}
{colored('║', Colors.CYAN)}  {colored('🤖 AutoAI', Colors.BOLD + Colors.MAGENTA)}  {colored('— Intelligent Typing Assistant', Colors.WHITE)}                {colored('║', Colors.CYAN)}
{colored('║', Colors.CYAN)}  {colored('Auto-Correct • Predict • Learn', Colors.GRAY)}                          {colored('║', Colors.CYAN)}
{colored('╚══════════════════════════════════════════════════════════════╝', Colors.CYAN)}
"""
    print(banner)


def print_divider(char="─", length=62):
    print(colored(char * length, Colors.GRAY))


def print_section(title, icon="▸"):
    print(f"\n{colored(icon, Colors.CYAN)} {colored(title, Colors.BOLD + Colors.WHITE)}")
    print_divider()


# ─── Core Demo Class ─────────────────────────────────────────────
class AutoAIDemo:
    """Interactive demo of the AutoAI typing assistant."""

    def __init__(self):
        # Initialize components with a status message
        print(f"  {colored('⚙', Colors.CYAN)} Loading system components and dictionary...")
        
        self.dictionary = Dictionary()
        dict_path = os.path.join('data', 'dictionaries', 'english.txt')
        if os.path.exists(dict_path):
            self.dictionary.load_from_file(dict_path)
            # Add some common abbreviations that might be missing or useful
            for word in ['r', 'u', 'ur', 'ok', 'idk', 'omw', 'brb', 'lol', 'thx']:
                self.dictionary.add_word(word, 100)
        
        self.corrector = AutoCorrector(dictionary=self.dictionary, max_edit_distance=2)
        self.predictor = WordPredictor(n=3)
        self.learner = UserLearner(UserProfile(user_id="demo_user"), dictionary=self.dictionary)

        # Train with some initial corpus
        self._train_initial_corpus()

        # Stats
        self.total_words_typed = 0
        self.total_corrections = 0
        self.session_texts = []

    def _train_initial_corpus(self):
        """Train the predictor with some initial text data."""
        corpus = [
            "I am going to the store to buy some groceries",
            "How are you doing today I hope you are well",
            "The weather is very nice today and I want to go outside",
            "I love programming in python because it is easy to learn",
            "Machine learning and artificial intelligence are the future",
            "I want to build a typing assistant that helps people type faster",
            "The quick brown fox jumps over the lazy dog",
            "Good morning how are you doing today",
            "I am working on a new project for my computer science class",
            "Thank you very much for your help I really appreciate it",
            "Can you help me with this problem I am stuck",
            "I think we should go to the park this weekend",
            "The data shows that the model is performing well",
            "I need to fix this bug in my code before the deadline",
            "Let us work together to make this system better",
            "I am learning about natural language processing",
            "The user interface needs to be more intuitive",
            "We should focus on improving the prediction accuracy",
            "I have been working on this for a long time",
            "The system is designed to learn from user input",
            "Hello world this is my first program",
            "I am happy to see you here today",
            "What do you think about this new feature",
            "I would like to know more about machine learning",
            "The keyboard is the most important input device",
        ]
        for text in corpus:
            self.predictor.train(text)

    def auto_correct_demo(self, text):
        """Run auto-correction on input text and display results."""
        words = text.split()
        corrected_words = []
        corrections_made = []

        for word in words:
            corrected = self.corrector.correct(word)
            corrected_words.append(corrected)

            if corrected.lower() != word.lower():
                corrections_made.append((word, corrected))
                self.total_corrections += 1

        corrected_text = " ".join(corrected_words)

        # Display results
        print_section("Auto-Correction", "✏️")

        if corrections_made:
            print(f"  {colored('Original:', Colors.RED)}  {text}")
            print(f"  {colored('Corrected:', Colors.GREEN)} {corrected_text}")
            print()
            for original, fixed in corrections_made:
                print(f"    {colored(original, Colors.RED + Colors.BOLD)} → {colored(fixed, Colors.GREEN + Colors.BOLD)}")
        else:
            print(f"  {colored('✓', Colors.GREEN)} No corrections needed — all words are valid!")

        return corrected_text

    def prediction_demo(self, text):
        """Run next-word prediction and display results."""
        print_section("Next-Word Predictions", "🔮")

        predictions = self.predictor.predict_next(text, top_k=5)

        if predictions:
            # Show predictions as a horizontal bar chart
            max_prob = predictions[0][1] if predictions else 1
            for i, (word, prob) in enumerate(predictions):
                bar_length = int((prob / max_prob) * 25)
                bar = "█" * bar_length + "░" * (25 - bar_length)

                rank_color = [Colors.GREEN, Colors.CYAN, Colors.BLUE, Colors.YELLOW, Colors.GRAY][i]
                rank_icon = ["🥇", "🥈", "🥉", " 4.", " 5."][i]

                print(f"  {rank_icon} {colored(word, rank_color + Colors.BOLD):.<20s} {colored(bar, rank_color)} {colored(f'{prob:.1%}', Colors.WHITE)}")
        else:
            print(f"  {colored('⚠', Colors.YELLOW)} Not enough context for prediction yet. Type more!")

        # Show sentence completion
        if predictions:
            top_word = predictions[0][0]
            print(f"\n  {colored('💡 Suggested:', Colors.MAGENTA)} \"{text} {colored(top_word, Colors.GREEN + Colors.BOLD)}\"")

    def learn_from_input(self, text):
        """Learn from user input and show what was learned."""
        self.learner.learn_from_text(text)
        self.predictor.train(text)

        words = text.lower().split()
        self.total_words_typed += len(words)
        self.session_texts.append(text)

        print_section("Learning", "🧠")
        print(f"  {colored('✓', Colors.GREEN)} Learned {colored(str(len(words)), Colors.CYAN + Colors.BOLD)} words from your input")
        print(f"  {colored('✓', Colors.GREEN)} Updated personal language model")
        print(f"  {colored('✓', Colors.GREEN)} Word pairs recorded for better predictions")

    def show_stats(self):
        """Display session statistics."""
        print_section("Session Stats", "📊")

        top_words = self.learner.profile.get_frequent_words(top_k=10)

        print(f"  {colored('Words typed:', Colors.CYAN)}       {colored(str(self.total_words_typed), Colors.WHITE + Colors.BOLD)}")
        print(f"  {colored('Corrections made:', Colors.CYAN)}  {colored(str(self.total_corrections), Colors.WHITE + Colors.BOLD)}")
        print(f"  {colored('Sentences:', Colors.CYAN)}         {colored(str(len(self.session_texts)), Colors.WHITE + Colors.BOLD)}")
        print(f"  {colored('Vocab size:', Colors.CYAN)}        {colored(str(self.predictor.model.vocab_size), Colors.WHITE + Colors.BOLD)}")

        if top_words:
            print(f"\n  {colored('Your most used words:', Colors.YELLOW)}")
            for word, count in top_words[:5]:
                bars = "●" * min(count, 15)
                print(f"    {colored(word, Colors.WHITE):.<15s} {colored(bars, Colors.GREEN)} ({count})")

    def show_help(self):
        """Display help information."""
        print_section("Commands", "❓")
        commands = [
            ("Type any text", "Auto-correct + predict + learn"),
            ("/predict <words>", "Get predictions for specific context"),
            ("/correct <text>", "Only auto-correct (no learning)"),
            ("/stats", "View session statistics"),
            ("/vocab", "Show your learned vocabulary"),
            ("/help", "Show this help menu"),
            ("/quit", "Exit the demo"),
        ]
        for cmd, desc in commands:
            print(f"  {colored(cmd, Colors.CYAN + Colors.BOLD):.<30s} {colored(desc, Colors.GRAY)}")

    def show_vocab(self):
        """Show the user's learned vocabulary."""
        print_section("Your Vocabulary", "📚")
        top_words = self.learner.profile.get_frequent_words(top_k=20)

        if not top_words:
            print(f"  {colored('No words learned yet. Start typing!', Colors.YELLOW)}")
            return

        # Display in a grid
        for i in range(0, len(top_words), 4):
            row = top_words[i:i+4]
            row_str = "  "
            for word, count in row:
                row_str += f"{colored(word, Colors.GREEN)}({colored(str(count), Colors.GRAY)})  "
            print(row_str)

    def process_input(self, user_input):
        """Process user input — main logic."""
        text = user_input.strip()

        if not text:
            return True

        # Handle commands
        if text.startswith("/"):
            cmd = text.split()[0].lower()

            if cmd == "/quit" or cmd == "/exit":
                return False
            elif cmd == "/help":
                self.show_help()
            elif cmd == "/stats":
                self.show_stats()
            elif cmd == "/vocab":
                self.show_vocab()
            elif cmd == "/predict":
                context = text[len("/predict "):].strip()
                if context:
                    self.prediction_demo(context)
                else:
                    print(f"  {colored('Usage: /predict <words>', Colors.YELLOW)}")
            elif cmd == "/correct":
                context = text[len("/correct "):].strip()
                if context:
                    self.auto_correct_demo(context)
                else:
                    print(f"  {colored('Usage: /correct <text>', Colors.YELLOW)}")
            else:
                print(f"  {colored('Unknown command. Type /help for available commands.', Colors.RED)}")
        else:
            # Full pipeline: correct → predict → learn
            corrected = self.auto_correct_demo(text)
            self.prediction_demo(corrected)
            self.learn_from_input(corrected)

        return True

    def run(self):
        """Main demo loop."""
        clear_screen()
        print_banner()

        print(f"  {colored('Welcome!', Colors.GREEN + Colors.BOLD)} Type anything and watch AutoAI in action.")
        print(f"  The system will {colored('correct', Colors.RED)} typos, {colored('predict', Colors.BLUE)} next words,")
        print(f"  and {colored('learn', Colors.MAGENTA)} from your typing style.\n")
        print(f"  Type {colored('/help', Colors.CYAN)} for commands or just start typing!\n")
        print_divider("═")

        running = True
        while running:
            try:
                prompt = f"\n{colored('⌨', Colors.CYAN)}  {colored('You:', Colors.BOLD)} "
                user_input = input(prompt)
                running = self.process_input(user_input)
            except KeyboardInterrupt:
                running = False
            except EOFError:
                running = False

        # Goodbye
        print(f"\n{colored('═' * 62, Colors.GRAY)}")
        self.show_stats()
        print(f"\n  {colored('👋 Thanks for trying AutoAI! See you next time.', Colors.MAGENTA + Colors.BOLD)}\n")


# ─── Entry Point ─────────────────────────────────────────────────
if __name__ == "__main__":
    demo = AutoAIDemo()
    demo.run()
