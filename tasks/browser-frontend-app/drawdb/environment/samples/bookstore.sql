CREATE TABLE `authors` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(120) NOT NULL,
  `born` DATE,
  PRIMARY KEY (`id`)
) COMMENT='writers';

CREATE TABLE `books` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `author_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `price` DECIMAL(6,2) DEFAULT 0,
  FOREIGN KEY (`author_id`) REFERENCES `authors`(`id`) ON DELETE CASCADE
);

CREATE INDEX `books_title` ON `books` (`title`);
