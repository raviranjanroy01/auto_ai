from setuptools import setup, find_packages

setup(
    name="auto_ai",
    version="0.1.0",
    description="AI-powered typing assistant with auto-correction and next-word prediction",
    author="raviranjanroy01",
    author_email="raviranjanroy1252@gmail.com",
    url="https://github.com/raviranjanroy01/auto_ai",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "nltk>=3.8.1",
        "numpy>=1.24.0",
        "regex>=2023.12.25",
        "pyyaml>=6.0.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
