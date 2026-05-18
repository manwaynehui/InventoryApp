import pandas as pd
from app import application, database
from models import Product

def initialize_database():
    with application.app_context():
        print("Cleaning old database and applying new structure...")
        database.drop_all()
        database.create_all()

        try:
            data_frame = pd.read_csv('IES_Inventory_Final_Updated.csv')
            products_to_add = []
            seen_item_numbers = set()

            for index, row in data_frame.iterrows():
                item_number = str(row['Item Number']).strip()
                if item_number in seen_item_numbers:
                    continue
                seen_item_numbers.add(item_number)

                raw_stock = row['In Stock']
                clean_stock = float(raw_stock) if (pd.notna(raw_stock) and str(raw_stock).strip() != "") else 0.0

                raw_price = row['List']
                price = float(raw_price) if pd.notna(raw_price) else 0.0

                new_product = Product(
                    item_number=item_number,
                    description=str(row['Description']) if pd.notna(row['Description']) else "No Description",
                    price=price,
                    in_stock=clean_stock
                )
                products_to_add.append(new_product)

            database.session.bulk_save_objects(products_to_add)
            database.session.commit()
            print(f"Success! Imported {len(seen_item_numbers)} items.")
        except FileNotFoundError:
            print("Error: CSV file 'IES_Inventory_Final_Updated.csv' not found.")
        except Exception as error:
            print(f"An error occurred: {error}")

if __name__ == "__main__":
    initialize_database()