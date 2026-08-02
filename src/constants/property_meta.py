PROPERTY_CATEGORIES = [
    'property',
    'land',
    'hotel',
    'hall',
    'event_center',
    'shortlet',
    'other'
]

PROPERTY_PURPOSES = [
    'rent',
    'sale',
    'both'
]

# Categories that support management sub-resources.
ROOM_CATEGORIES = [
    'hotel',
]

SLOT_CATEGORIES = [
    'hall',
    'event_center',
]

BOOKING_CATEGORIES = [
    'hotel',
    'hall',
    'event_center',
    'shortlet',
]

SLOT_STATUSES = [
    'available',
    'pending',
    'booked',
]

BOOKING_STATUSES = [
    'pending',
    'confirmed',
    'cancelled',
    'completed',
]

# Suggested keys for the flexible `attributes` JSON column per category.
# These are hints only - clients may supply any keys they like.
CATEGORY_ATTRIBUTE_HINTS = {
    'property': {
        'furnished': 'boolean',
        'furnishing_status': 'string',
        'title_document': 'string',
        'number_of_floors': 'integer',
        'road_access': 'boolean',
    },
    'land': {
        'plot_size': 'number',
        'land_title': 'string',
        'plot_number': 'string',
        'fenced': 'boolean',
        'water_source': 'boolean',
        'electricity': 'boolean',
        'use_permit': 'boolean',
    },
    'hotel': {
        'star_rating': 'integer',
        'number_of_rooms': 'integer',
        'room_types': 'array',
        'check_in_time': 'string',
        'check_out_time': 'string',
        'services': 'array',
        'food_options': 'boolean',
        'parking_spaces': 'integer',
    },
    'hall': {
        'capacity': 'integer',
        'standing_capacity': 'integer',
        'parking_spaces': 'integer',
        'sound_system': 'boolean',
        'lighting': 'boolean',
        'ac': 'boolean',
        'backup_power': 'boolean',
        'booking_duration': 'string',
    },
    'event_center': {
        'capacity': 'integer',
        'standing_capacity': 'integer',
        'parking_spaces': 'integer',
        'sound_system': 'boolean',
        'lighting': 'boolean',
        'ac': 'boolean',
        'backup_power': 'boolean',
        'changing_room': 'boolean',
        'booking_duration': 'string',
    },
    'shortlet': {
        'furnished': 'boolean',
        'minimum_stay_nights': 'integer',
        'maximum_stay_nights': 'integer',
        'check_in_time': 'string',
        'check_out_time': 'string',
        'cleaning_fee': 'number',
        'service_fee': 'number',
    },
    'other': {},
}


def is_valid_category(category):
    return category in PROPERTY_CATEGORIES


def is_valid_purpose(purpose):
    return purpose in PROPERTY_PURPOSES
