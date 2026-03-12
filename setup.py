from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="seeed-jetson-develop",
    version="0.2.0",
    author="Seeed Studio",
    author_email="support@seeedstudio.com",
    description="Seeed Jetson Develop Tool — 烧录、设备管理、应用市场、Skills、远程开发",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Seeed-Studio/seeed-jetson-develop",
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
            "seeed-jetson-develop=seeed_jetson_develop.cli:main",
        ],
    },
    package_data={
        "seeed_jetson_develop": [
            "data/*.json",
            "assets/images/*",
            "modules/apps/data/*.json",
            "modules/skills/data/*.json",
        ],
    },
)
