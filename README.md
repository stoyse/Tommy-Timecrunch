# Tommy Timecrunch Flask App

A simple Flask web application with template rendering functionality.

## Features

- Home page with feature showcase
- About page with detailed information
- Contact page with contact form and information
- Responsive design using Bootstrap
- Template inheritance using Jinja2

## Setup and Installation

1. Install Python 3.x if not already installed
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to `http://localhost:5000`

## Project Structure

```
TommyTimecrunch/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── about.html        # About page
│   └── contact.html      # Contact page
└── static/               # Static files
    └── css/
        └── style.css     # Custom CSS styles
```

## Routes

- `/` - Home page
- `/about` - About page  
- `/contact` - Contact page

## Technologies Used

- Flask (Python web framework)
- Jinja2 (Template engine)
- Bootstrap 5 (CSS framework)
- HTML5 & CSS3
