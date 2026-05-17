CREATE TABLE IF NOT EXISTS gold.dim_category (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "category" VARCHAR(255) NOT NULL,
    "subcategory" VARCHAR(255)
);

DELETE FROM gold.dim_category;

INSERT OR IGNORE INTO gold.dim_category (id, category, subcategory)
SELECT id, category, subcategory
FROM mappings.categories;
