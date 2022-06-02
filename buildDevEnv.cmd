:: Create virtual environment for development

:: virtial env
virtualenv venv

:: Activate virtual env
call venv/Scripts/activate.bat

:: install requirements
pip install -r requirements.txt

:: install package:
pip install -e .
