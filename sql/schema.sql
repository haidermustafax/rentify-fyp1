CREATE DATABASE IF NOT EXISTS rentify_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE rentify_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'seller', 'admin') DEFAULT 'user',
    wallet_balance DECIMAL(10, 2) DEFAULT 0.00,
    is_verified BOOLEAN DEFAULT FALSE,
    otp_code VARCHAR(6) NULL,
    otp_expires_at DATETIME NULL,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO categories (id, name, slug) VALUES
(1, 'Home & Furniture', 'furniture'),
(2, 'Electronics', 'electronics'),
(3, 'Car Rentals', 'cars'),
(4, 'Event Venues & Equipment', 'events');

CREATE TABLE IF NOT EXISTS listings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    price_per_day DECIMAL(10, 2) NOT NULL,
    deposit_amount DECIMAL(10, 2) DEFAULT 0.00,
    location VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image_url VARCHAR(500) DEFAULT '/static/images/default.jpg',
    seller_id INT NULL,
    INDEX listings_category_id_idx (category_id),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO listings
    (category_id, title, description, price_per_day, deposit_amount, location, image_url, is_available)
SELECT seed.category_id, seed.title, seed.description, seed.price_per_day,
       seed.deposit_amount, seed.location, seed.image_url, TRUE
FROM (
    SELECT 1 AS category_id, 'Ergonomic Mesh Office Chair' AS title,
           'High-back mesh chair with adjustable armrests and lumbar support.' AS description,
           1500.00 AS price_per_day, 5000.00 AS deposit_amount, 'Karachi Central' AS location,
           '/static/images/furniture/chair.jpeg' AS image_url
    UNION ALL SELECT 2, 'Sony PS5 Console + 2 Controllers',
           'PlayStation 5 digital edition with 2 DualSense controllers and preloaded games.',
           3500.00, 10000.00, 'DHA Phase 6', '/static/images/electronics/ps5.jpeg'
    UNION ALL SELECT 3, 'Toyota Corolla Grandi 2023',
           'Automatic transmission, self-drive, full options, pristine condition.',
           18000.00, 40000.00, 'Clifton', '/static/images/cars/Toyota_Grande_2025.jpg'
    UNION ALL SELECT 4, 'Professional Stage Lighting Set',
           'Includes 4 PAR LED lights, stand, and DMX controller for indoor/outdoor events.',
           11000.00, 25000.00, 'PECHS', '/static/images/furniture/lights.jpeg'
    UNION ALL SELECT 1, 'Sofa Lounge Set',
           'Stylish sofa set for modern living rooms and short-term staging.',
           2600.00, 8000.00, 'Gulshan', '/static/images/furniture/sofa.jpeg'
    UNION ALL SELECT 2, 'Gaming Laptop',
           'Powerful high-refresh laptop for creators and gamers.',
           4200.00, 15000.00, 'Bahria Town', '/static/images/electronics/gaminglaptop.jpeg'
    UNION ALL SELECT 3, 'Lexus 570hs',
           'Luxury SUV experience with comfort and sporty performance.',
           26000.00, 70000.00, 'Clifton', '/static/images/cars/Lexus_570hs_2021.png'
    UNION ALL SELECT 2, 'Air Conditioner Unit',
           'Powerful cooling solution for homes, events and offices.',
           2800.00, 12000.00, 'Nazimabad', '/static/images/electronics/airconditioner.jpeg'
    UNION ALL SELECT 4, 'Wedding LED Booth',
           'Premium backdrop setup for events and launches.',
           9000.00, 22000.00, 'Karachi Expo', '/static/images/furniture/lights.jpeg'
    UNION ALL SELECT 1, 'Modern Dining Set',
           'Contemporary and durable dining furniture for rental spaces.',
           2200.00, 7500.00, 'Garden East', '/static/images/furniture/4seatertable.jpeg'
    UNION ALL SELECT 3, 'Audi A3',
           'Compact luxury sedan with excellent city drive experience.',
           17000.00, 45000.00, 'Sea View', '/static/images/cars/audi_a3.png'
    UNION ALL SELECT 2, 'Xbox Series X',
           'Gaming console package for entertainment and events.',
           4000.00, 11000.00, 'DHA', '/static/images/electronics/xboxseriesx.jpeg'
    UNION ALL SELECT 1, 'Glass Dining Table',
           'Premium glass top dining table for stylish rental properties.',
           2400.00, 7000.00, 'Clifton', '/static/images/furniture/glass.jpeg'
    UNION ALL SELECT 2, 'Smart Television',
           'Large smart TV with streaming support and cinematic display.',
           3100.00, 10000.00, 'North Karachi', '/static/images/electronics/television.jpeg'
    UNION ALL SELECT 4, 'Party Tent Package',
           'Premium tent setup for weddings and family functions.',
           12500.00, 27000.00, 'Malir', '/static/images/furniture/lights.jpeg'
    UNION ALL SELECT 3, 'Toyota Revo GR 2026',
           'Adventure-ready SUV with premium interior and practical comfort.',
           32000.00, 90000.00, 'Jinnah Avenue', '/static/images/cars/Revo_GR_2026.png'
    UNION ALL SELECT 2, 'Microwave & Oven Combo',
           'Compact kitchen appliance bundle for rentals and residences.',
           2600.00, 8000.00, 'Gulshan', '/static/images/electronics/microwave.jpeg'
    UNION ALL SELECT 1, 'Gaming Chair',
           'Comfortable racing chair for live streaming and home office setups.',
           1800.00, 6000.00, 'Federal B Area', '/static/images/furniture/gamingchair.jpeg'
) AS seed
LEFT JOIN listings existing
    ON existing.category_id = seed.category_id AND existing.title = seed.title
WHERE existing.id IS NULL;
