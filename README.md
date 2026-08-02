# Aperte API

## Overview
The **Aperte API** is a web application built with Python and Flask that provides a platform for listing and managing property advertisements. The API supports user and admin roles with JWT-based authentication, allowing users to securely upload, list, and manage properties — from rent and sale listings (land, houses, apartments, offices) to hotels, halls, event centers, and shortlets.

## Features
- **JWT Token Authentication**:
  - Secure authentication for users via access and refresh tokens.
  - Email verification with expiring 6-digit codes.
- **User Roles**:
  - **Users**:
    - Upload property listings with details such as title, description, price, location, and flexible type-specific attributes.
    - View and manage their uploaded listings.
    - Upload/delete a profile picture.
    - Post "requests" describing the property they are looking for.
    - Review and rate properties.
  - **Admins**:
    - Manage all listings.
    - Perform administrative tasks like approving or removing listings.
- **Flexible Property Types**:
  - Every listing carries a `category`, `purpose`, and a flexible `attributes` object, so each type can store its own fields without schema changes.
  - Supported categories: `property`, `land`, `hotel`, `hall`, `event_center`, `shortlet`, `other`.
  - Supported purposes: `rent`, `sale`, `both`.
  - `attributes` examples: `plot_size`/`land_title` for land, `capacity`/`sound_system` for halls and event centers, `star_rating`/`number_of_rooms` for hotels, `minimum_stay_nights`/`furnished` for shortlets.
- **Property Management**:
  - Add, edit, view, and delete property advertisements.
  - Upload/delete multiple images (with a display picture) and videos for a listing.
- **Category Management**:
  - **Hotels** manage bookable `rooms` (room type, beds, nightly price, amenities).
  - **Halls / Event centers** manage time `slots` (date, start/end time, price) with overlap protection.
  - **Hotel, hall, event_center, and shortlet** properties accept `bookings`. Customers request a booking, owners confirm or complete it, either party can cancel. Availability conflicts are rejected automatically.
- **Property Search**:
  - Browse and search listings with filters such as category, purpose, property type, city, state, country, and price range.

## API Documentation
Interactive Swagger documentation is available at the root path (`/`), with the JSON spec at `/apispec.json`.

### Endpoints
All endpoints are prefixed with `/api/v1`.

#### Authentication
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/auth/register` | Register a new user and send a verification email |
| POST | `/auth/login` | Log in (username, email, or phone number) |
| POST | `/auth/verifyemail/{email}` | Verify email with the 6-digit code |
| GET | `/auth/resendverify/{email}` | Resend the email verification code |
| GET | `/auth/user` | Get the authenticated user's details |
| GET | `/auth/token/refresh` | Refresh the access token |
| GET | `/auth/forgotpassword/{email}` | Request a password reset code |
| POST | `/auth/resetpassword/{email}` | Reset the password with the code |

#### Users
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| PUT/PATCH | `/users/` | Edit the authenticated user's profile |
| POST | `/users/dp` | Upload a profile picture |
| DELETE | `/users/dp` | Remove the profile picture |

#### Properties
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/properties/` | Create a property listing |
| GET | `/properties/` | Browse listings with filters (category, purpose, property_type, city, state, country, min_price, max_price) |
| GET | `/properties/{id}` | Get a single listing |
| GET | `/properties/user/{id}/` | Get all listings of a user (paginated) |
| PUT/PATCH | `/properties/{id}` | Edit a listing |
| POST | `/properties/images/{id}` | Add images to a listing |
| DELETE | `/properties/images/{id}` | Delete an image from a listing |
| POST | `/properties/videos/{id}` | Add videos to a listing |
| DELETE | `/properties/videos/{id}` | Delete a video from a listing |

#### Requests
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/requests/` | Create a property request |
| GET | `/requests/{id}` | Get a single request |
| GET | `/requests/user/{id}/` | Get all requests of a user (paginated) |
| PUT/PATCH | `/requests/{id}` | Edit a request |
| DELETE | `/requests/{id}` | Delete a request |

#### Reviews
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/reviews/{id}` | Review a property (id = property id) |
| GET | `/reviews/{id}` | Get a single review |
| GET | `/reviews/properties/{id}` | Get all reviews for a property (paginated) |
| GET | `/reviews/` | Get the authenticated user's reviews (paginated) |
| DELETE | `/reviews/{id}` | Delete a review |

#### Rooms (hotel)
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/rooms/property/{property_id}` | Add a room to a hotel property (owner) |
| GET | `/rooms/property/{property_id}` | List rooms of a property |
| GET | `/rooms/{id}` | Get a single room |
| PUT/PATCH | `/rooms/{id}` | Edit a room (owner) |
| DELETE | `/rooms/{id}` | Delete a room (owner; blocked while booked) |

#### Slots (hall / event_center)
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/slots/property/{property_id}` | Create a time slot (owner) |
| GET | `/slots/property/{property_id}` | List slots, filter by `date` and `status` |
| GET | `/slots/{id}` | Get a single slot |
| PUT/PATCH | `/slots/{id}` | Edit a slot (owner; blocked while pending/booked) |
| DELETE | `/slots/{id}` | Delete a slot (owner; blocked while pending/booked) |

#### Bookings (hotel, hall, event_center, shortlet)
| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| POST | `/bookings/property/{property_id}` | Request a booking (requires `room_id` for hotels, `slot_id` for halls/event centers, dates for hotels/shortlets) |
| GET | `/bookings/{id}` | Get a single booking |
| GET | `/bookings/property/{property_id}` | List a property's bookings (owner) |
| GET | `/bookings/user/{user_id}/` | List a user's bookings |
| PUT/PATCH | `/bookings/{id}` | Change status: owner confirms/completes, owner or customer cancels |
| DELETE | `/bookings/{id}` | Delete a booking (owner or customer) |

## Technologies Used
- **Backend**: Python (Flask)
- **Authentication**: JSON Web Tokens (JWT)
- **Database**: SQLite (configurable for PostgreSQL/MySQL)
- **API Structure**: RESTful
- **Documentation**: Swagger / Flasgger
- **Object Storage**: Cloudflare R2 (images, videos, profile pictures)
- **Language**: Python

## Cloudflare R2 Object Storage
All file uploads (property images, property videos, and user profile pictures) are stored in Cloudflare R2 instead of the local filesystem. Configuration is via environment variables (in `.flaskenv` locally, or the host's environment on deployment):

| Variable | Description |
| -------- | ----------- |
| `R2_ACCOUNT_ID` | Cloudflare account ID (used to build the S3-compatible endpoint) |
| `R2_ACCESS_KEY_ID` | R2 API token access key ID |
| `R2_SECRET_ACCESS_KEY` | R2 API token secret access key |
| `R2_BUCKET_NAME` | Bucket name to store objects in |
| `R2_PUBLIC_BASE_URL` | Public base URL for objects (custom domain or the bucket's `.r2.dev` URL) |

The R2 S3-compatible endpoint is built as `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`. Objects are stored under keys like `properties/<user_id>/images/...`, `properties/<user_id>/videos/...`, and `users/<user_id>/dp/...`, and the full public URL is saved in the database (`image_url`, `video_url`, `profile_picture`). Legacy local filesystem paths are ignored on delete, so pre-existing data is unaffected.
