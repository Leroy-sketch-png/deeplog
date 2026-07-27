import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="deeplog-analytics",
    version="1.0.0",
    description="Behavioral anomaly detection for Azure Activity Logs — deterministic, explainable, SOC-ready.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Leroy-sketch-png/deeplog",
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.21",
    ],
    entry_points={
        "console_scripts": [
            "deeplog=deeplog.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
        "Topic :: System :: Logging",
    ],
)
