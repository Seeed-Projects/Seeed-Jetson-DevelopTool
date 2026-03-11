from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="seeed-jetson-flash",
    version="0.1.0",
    author="Seeed Studio",
    author_email="support@seeedstudio.com",
    description="A tool for flashing Jetson devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Seeed-Studio/seeed-jetson-flash",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.6",
    install_requires=[
        "requests>=2.25.0",
        "tqdm>=4.60.0",
        "click>=8.0.0",
        "rich>=10.0.0",
        "PyQt5>=5.15.0",
    ],
    entry_points={
        "console_scripts": [
            "seeed-jetson-flash=seeed_jetson_flash.cli:main",
        ],
    },
    package_data={
        "seeed_jetson_flash": ["data/*.json", "assets/images/*"],
    },
)
