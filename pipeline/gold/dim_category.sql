INSERT OR IGNORE INTO gold.dim_category (id, category, subcategory)
SELECT id, category, subcategory
FROM mappings.categories;
