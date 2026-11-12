CREATE DATABASE IF NOT EXISTS ecommerce_db;
USE ecommerce_db;

CREATE TABLE IF NOT EXISTS customers (
  customer_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  phone VARCHAR(30),
  country VARCHAR(80),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categories (
  category_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  category_name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
  product_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  category_id BIGINT,
  product_name VARCHAR(160) NOT NULL,
  description TEXT,
  sku VARCHAR(60) NOT NULL UNIQUE,
  price DECIMAL(12,2) NOT NULL,
  stock_quantity INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_products_category FOREIGN KEY (category_id)
    REFERENCES categories(category_id) ON DELETE SET NULL,
  CONSTRAINT chk_product_price CHECK (price >= 0),
  CONSTRAINT chk_product_stock CHECK (stock_quantity >= 0),
  INDEX idx_products_name (product_name),
  INDEX idx_products_category (category_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
  order_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id BIGINT NOT NULL,
  order_status ENUM('PENDING','CONFIRMED','SHIPPED','DELIVERED','CANCELLED') DEFAULT 'PENDING',
  total_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
    REFERENCES customers(customer_id),
  INDEX idx_orders_created (created_at),
  INDEX idx_orders_customer (customer_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  quantity INT NOT NULL,
  unit_price DECIMAL(12,2) NOT NULL,
  CONSTRAINT fk_items_order FOREIGN KEY (order_id)
    REFERENCES orders(order_id) ON DELETE CASCADE,
  CONSTRAINT fk_items_product FOREIGN KEY (product_id)
    REFERENCES products(product_id),
  CONSTRAINT chk_item_quantity CHECK (quantity > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
  payment_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  payment_method ENUM('CARD','UPI','NETBANKING','CASH') NOT NULL,
  payment_status ENUM('PENDING','SUCCESS','FAILED','REFUNDED') DEFAULT 'PENDING',
  transaction_reference VARCHAR(120),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id)
    REFERENCES orders(order_id),
  INDEX idx_payment_order (order_id)
) ENGINE=InnoDB;

INSERT IGNORE INTO categories(category_id, category_name) VALUES
(1,'Electronics'),(2,'Fashion'),(3,'Home & Kitchen'),(4,'Books');

INSERT IGNORE INTO customers(customer_id,full_name,email,phone,country) VALUES
(1,'Aarav Sharma','aarav@example.com','9000000001','India'),
(2,'Priya Reddy','priya@example.com','9000000002','India'),
(3,'John Smith','john@example.com','9000000003','USA');

INSERT IGNORE INTO products(product_id,category_id,product_name,description,sku,price,stock_quantity) VALUES
(1,1,'Wireless Headphones','Bluetooth over-ear headphones','ELEC-1001',2499.00,50),
(2,1,'Mechanical Keyboard','RGB mechanical keyboard','ELEC-1002',3299.00,35),
(3,2,'Cotton T-Shirt','Everyday cotton T-shirt','FASH-2001',699.00,100),
(4,3,'Coffee Maker','Automatic drip coffee maker','HOME-3001',4599.00,20),
(5,4,'SQL for Beginners','Database fundamentals book','BOOK-4001',599.00,75);

-- Useful reporting view
CREATE OR REPLACE VIEW v_country_sales AS
SELECT c.country, COUNT(DISTINCT o.order_id) AS total_orders,
       COALESCE(SUM(o.total_amount),0) AS total_sales
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.country;

-- Example stored procedure for country-wise customer counts
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS sp_customer_count_by_country(IN p_country VARCHAR(80))
BEGIN
  SELECT country, COUNT(*) AS customer_count
  FROM customers
  WHERE country = p_country
  GROUP BY country;
END //
DELIMITER ;
