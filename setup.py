from setuptools import setup, find_packages

setup(
    name="desktop-gboard",
    version="0.2.0",
    description="Desktop G-Board — Global AI typing assistant with prediction, autocorrect, and code assistance",
    author="raviranjanroy01",
    author_email="raviranjanroy1252@gmail.com",
    url="https://github.com/raviranjanroy01/auto_ai",
    packages=find_packages(exclude=["tests*", "scripts*", "docs*"]),
    python_requires=">=3.9",
    install_requires=[
        "nltk>=3.8.1",
        "numpy>=1.24.0",
        "regex>=2023.12.25",
        "pyyaml>=6.0.1",
        "pynput>=1.7.6",
        "pyperclip>=1.8.2",
        "psutil>=5.9.0",
    ],
    extras_require={
        "ui": [
            "PySide6>=6.5.0",
            "pystray>=0.19.4",
            "Pillow>=10.0.0",
        ],
        "cloud": [
            "anthropic>=0.25.0",
            "openai>=1.12.0",
        ],
        "local-llm": [
            "llama-cpp-python>=0.2.0",
        ],
        "onnx": [
            "onnxruntime>=1.17.0",
        ],
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
        "all": [
            "PySide6>=6.5.0",
            "pystray>=0.19.4",
            "Pillow>=10.0.0",
            "anthropic>=0.25.0",
            "openai>=1.12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "desktop-gboard=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Text Processing :: Linguistic",
    ],
)
