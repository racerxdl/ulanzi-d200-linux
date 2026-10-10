from setuptools import setup, find_packages

setup(
    name="ulanzi-manager",
    version="0.1.0",
    description="Ulanzi D200 StreamDeck device manager for Linux",
    author="Lucas",
    packages=find_packages(exclude=["ulanzi_manager.static", "ulanzi_manager.static.*"]),
    include_package_data=True,
    package_data={"ulanzi_manager": ["static/*.html", "static/*.css", "static/*.js",
                                     "static/fonts/*.ttf", "static/fonts/LICENSE*"]},
    install_requires=[
        "hidapi==0.15.0",
        "pyyaml==6.0.1",
        "obsws-python==1.8.0",
        "pillow==12.3.0",
    ],
    entry_points={
        "console_scripts": [
            "ulanzi-manager=ulanzi_manager.cli:main",
            "ulanzi-daemon=ulanzi_manager.daemon:main",
            "ulanzi-web=ulanzi_manager.web:main",
        ],
    },
    python_requires=">=3.10",
)
