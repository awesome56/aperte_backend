# Apartment Listing API

## Overview
The **Apartment Listing API** is a web application built with Python and Flask that provides a platform for managing apartment listings. The API supports user and admin roles with JWT-based authentication, allowing users to securely upload, list, and manage properties as advertisements.

## Features
- **JWT Token Authentication**:
  - Secure authentication for both users and admins.
- **User Roles**:
  - **Users**:
    - Upload property listings with details such as title, description, price, and location.
    - View and manage their uploaded listings.
  - **Admins**:
    - Manage all listings.
    - Perform administrative tasks like approving or removing listings.
- **Property Management**:
  - Add, edit, delete, and view property advertisements.
- **Property Search**:
  - Search for properties by filters such as price, location, and property type.

## Technologies Used
- **Backend**: Python (Flask)
- **Authentication**: JSON Web Tokens (JWT)
- **Database**: SQLite (configurable for PostgreSQL/MySQL)
- **API Structure**: RESTful
- **Language**: Python
