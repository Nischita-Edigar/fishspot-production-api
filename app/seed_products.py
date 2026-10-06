from sqlmodel import Session, select

from app.database import engine, create_db_and_tables
from app.models import Product


# Approximate development prices.
# These are NOT final Fish Spot Malpe prices.
# The owner will update each product price from the admin panel.

MENU_ROWS = [
    ('Basa', '-', '1 to 4.5 kg', 'fry cut', '', 'Fresh Water Fish', 240),
    ('Basa', '-', '1 to 4.5 kg', 'Boneless cubes', '', 'Fresh Water Fish', 310),
    ('Basa', '-', '1 to 4.5 kg', 'Fillet', '', 'Fresh Water Fish', 310),
    ('Rohu', 'SMALL', '0.9-1.3 kg', 'Whole fish steaks', '', 'Fresh Water Fish', 300),
    ('Rohu', 'SMALL', '0.9-1.3 kg', 'Bengali cut with head', '', 'Fresh Water Fish', 220),
    ('Rohu', 'SMALL', '0.9-1.3 kg', 'peti cut', '', 'Fresh Water Fish', 270),
    ('Rohu', 'SMALL', '0.9-1.3 kg', 'Bengali cut without head', '', 'Fresh Water Fish', 240),
    ('Rohu', 'MEDIUM', '1.3- 2KG', 'Whole fish steaks', '', 'Fresh Water Fish', 340),
    ('Rohu', 'MEDIUM', '1.3- 2KG', 'Bengali cut with head', '', 'Fresh Water Fish', 260),
    ('Rohu', 'MEDIUM', '1.3- 2KG', 'peti cut', '', 'Fresh Water Fish', 310),
    ('Rohu', 'MEDIUM', '1.3- 2KG', 'Bengali cut without head', '', 'Fresh Water Fish', 280),
    ('Rohu', 'LARGE', '2-3KG', 'Whole fish steaks', '', 'Fresh Water Fish', 460),
    ('Rohu', 'LARGE', '2-3KG', 'Bengali cut with head', '', 'Fresh Water Fish', 380),
    ('Rohu', 'LARGE', '2-3KG', 'peti cut', '', 'Fresh Water Fish', 430),
    ('Rohu', 'LARGE', '2-3KG', 'Bengali cut without head', '', 'Fresh Water Fish', 330),
    ('Rohu', '-', '', 'HEAD', '', 'Fresh Water Fish', 190),
    ('Catla', 'SMALL', '0.9-1.5KG', 'Whole fish steaks', '', 'Fresh Water Fish', 280),
    ('Catla', 'SMALL', '0.9-1.5KG', 'Bengali cut with head', '', 'Fresh Water Fish', 210),
    ('Catla', 'SMALL', '0.9-1.5KG', 'peti cut', '', 'Fresh Water Fish', 260),
    ('Catla', 'SMALL', '0.9-1.5KG', 'Bengali cut without head', '', 'Fresh Water Fish', 230),
    ('Catla', 'MEDIUM', '1.5-2.5 KG', 'Whole fish steaks', '', 'Fresh Water Fish', 400),
    ('Catla', 'MEDIUM', '1.5-2.5 KG', 'Bengali cut with head', '', 'Fresh Water Fish', 250),
    ('Catla', 'MEDIUM', '1.5-2.5 KG', 'peti cut', '', 'Fresh Water Fish', 300),
    ('Catla', 'MEDIUM', '1.5-2.5 KG', 'Bengali cut without head', '', 'Fresh Water Fish', 270),
    ('Catla', 'LARGE', '2.5-4.5KG', 'Whole fish steaks', '', 'Fresh Water Fish', 440),
    ('Catla', 'LARGE', '2.5-4.5KG', 'Bengali cut with head', '', 'Fresh Water Fish', 370),
    ('Catla', 'LARGE', '2.5-4.5KG', 'peti cut', '', 'Fresh Water Fish', 420),
    ('Catla', 'LARGE', '2.5-4.5KG', 'Bengali cut without head', '', 'Fresh Water Fish', 390),
    ('Catla', '', '', 'HEAD', '', 'Fresh Water Fish', 180),
    ('Roopchand', 'SMALL', '0.5-1 KG', 'Whole fish steaks', '', 'Fresh Water Fish', 280),
    ('Roopchand', 'SMALL', '0.5-1 KG', 'Curry Cut', '', 'Fresh Water Fish', 260),
    ('Roopchand', 'SMALL', '0.5-1 KG', 'Bengali cut', '', 'Fresh Water Fish', 250),
    ('Roopchand', 'MEDIUM', '1-2 KG', 'Whole fish steaks', '', 'Fresh Water Fish', 380),
    ('Roopchand', 'MEDIUM', '1-2 KG', 'Curry Cut', '', 'Fresh Water Fish', 360),
    ('Roopchand', 'MEDIUM', '1-2 KG', 'Bengali cut', '', 'Fresh Water Fish', 350),
    ('Roopchand', 'LARGE', '2-3KG', 'Whole fish steaks', '', 'Fresh Water Fish', 420),
    ('Roopchand', 'LARGE', '2-3KG', 'Curry Cut', '', 'Fresh Water Fish', 400),
    ('Roopchand', 'LARGE', '2-3KG', 'Bengali cut', '', 'Fresh Water Fish', 390),
    ('Pabda', '-', '10-20 PCS/KG', 'Whole Cleaned & gutted', '2-5', 'Fresh Water Fish', 250),
    ('Murrel/River sole', '-', '0.8-3kg', 'Fry Cut', '', 'Fresh Water Fish', 280),
    ('Murrel/River sole', '-', '0.8-3kg', 'Fillet', '', 'Fresh Water Fish', 340),
    ('Tilapia', '-', '350-800 gm', 'Fillet', '', 'Fresh Water Fish', 350),
    ('Bhetki', '-', '2.5-3.5 kg', 'Curry cut', '', 'Fresh Water Fish', 240),
    ('Bhetki', '-', '2.5-3.5 kg', 'Boneless cubes', '', 'Fresh Water Fish', 310),
    ('Bhetki', '-', '-', 'Head', '', 'Fresh Water Fish', 200),
    ('Hilsa/llish', '-', '0.8-1 kg', 'Curry cut with head', '', 'Fresh Water Fish', 280),
    ('Parshe', '-', '5-10 Pieces/kg', 'whole cleaned', '1-3', 'Fresh Water Fish', 260),
    ('Pearl spot', '-', '5-10 Pieces/kg', 'whole cleaned', '1-3', 'Fresh Water Fish', 270),
    ('Fresh water prawns', 'SMALL', '80-110 Pieces/kg', 'Cleaned and deveined', '20-28', 'Prawns', 560),
    ('Fresh water prawns', 'MEDIUM', '40-60 Pieces', 'Cleaned and deveined', '', 'Prawns', 560),
    ('Fresh water prawns', 'LARGE', '30-40 Pieces', 'Cleaned and deveined', '', 'Prawns', 660),
    ('White sardine', '-', '90-120 Pieces', 'Whole cleaned', '', 'Sea Water Fish', 340),
    ('Sea Prawns', 'Medium', '40-60 Pieces', 'Cleaned and deveined', '', 'Prawns', 600),
    ('Sea Prawns', 'Large', '20-40 Pieces', 'Cleaned and deveined', '', 'Prawns', 640),
    ('Anchovy/Nathili/Kollataru', '-', '50-90 Pieces', 'whole cleaned', '', 'Sea Water Fish', 370),
    ('Indian Salmon', 'Medium', '0.7-3kg', 'Fry cut', '', 'Sea Water Fish', 470),
    ('Indian Salmon', '', '', 'Head & Tail', '', 'Sea Water Fish', 280),
    ('Boothai/Sardine/Mathi', 'Medium', '15-25 Pieces', 'Whole cleaned with head', '', 'Sea Water Fish', 400),
    ('Boothai/Sardine/Mathi', 'Medium', '15-25 Pieces', 'Whole cleaned without head', '', 'Sea Water Fish', 410),
    ('White Pomfret', 'SMALL', '100-150 Gms', 'Whole cleaned and gutted', '', 'Sea Water Fish', 350),
    ('White Pomfret', 'Medium', '250-450 Gms', 'Whole cleaned and gutted', '', 'Sea Water Fish', 430),
    ('White Pomfret', 'LARGE', '500 Gms-1 Kg', 'Whole cleaned and gutted', '', 'Sea Water Fish', 520),
    ('Bangude/Mackerel/Ayla', 'SMALL', '8-12 pcs/kg', 'Whole cleaned with head', '2-3', 'Sea Water Fish', 380),
    ('Bangude/Mackerel/Ayla', 'SMALL', '8-12 pcs/kg', 'Curry cut', '2-3', 'Sea Water Fish', 340),
    ('Bangude/Mackerel/Ayla', 'SMALL', '8-12 pcs/kg', 'Butterfly Cut', '2-3', 'Sea Water Fish', 360),
    ('Bangude/Mackerel/Ayla', 'Medium', '6-8 pcs/kg', 'Whole cleaned with head', '1-2', 'Sea Water Fish', 410),
    ('Bangude/Mackerel/Ayla', 'Medium', '6-8 pcs/kg', 'Curry cut', '1-2', 'Sea Water Fish', 440),
    ('Bangude/Mackerel/Ayla', 'Medium', '6-8 pcs/kg', 'Butterfly Cut', '1-2', 'Sea Water Fish', 460),
    ('Bangude/Mackerel/Ayla', 'LARGE', '3-5 pcs/kg', 'Whole cleaned with head', '0-2', 'Sea Water Fish', 520),
    ('Bangude/Mackerel/Ayla', 'LARGE', '3-5 pcs/kg', 'Curry cut', '0-2', 'Sea Water Fish', 560),
    ('Bangude/Mackerel/Ayla', 'LARGE', '3-5 pcs/kg', 'Butterfly Cut', '0-2', 'Sea Water Fish', 500),
    ('Anjal/Seer Fish/Vanjaram', 'SMALL', '0.5-1.5KG', '&#x20;steaks with head', '', 'Sea Water Fish', 380),
    ('Anjal/Seer Fish/Vanjaram', 'Medium', '3-5 kg', 'Thin Slices', '', 'Sea Water Fish', 410),
    ('Anjal/Seer Fish/Vanjaram', 'Medium', '3-5 kg', 'Fillets', '', 'Sea Water Fish', 490),
    ('Anjal/Seer Fish/Vanjaram', 'Medium', '3-5 kg', 'Curry cut with head', '', 'Sea Water Fish', 460),
    ('Anjal/Seer Fish/Vanjaram', 'LARGE', '5-10 kg', 'Thin Slices', '', 'Sea Water Fish', 520),
    ('Anjal/Seer Fish/Vanjaram', 'LARGE', '5-10 kg', 'Fillets', '', 'Sea Water Fish', 600),
    ('Anjal/Seer Fish/Vanjaram', '', '', 'Head & Tail', '', 'Sea Water Fish', 280),
    ('Tuna', '-', '0.5-1.5kg', 'Boneless cube', '', 'Sea Water Fish', 410),
    ('Tuna', '-', '0.5-1.5kg', 'Curry cut with head', '', 'Sea Water Fish', 360),
    ('Black Pomfret', 'SMALL', '250-450 gms', 'Curry cut with head', '', 'Sea Water Fish', 380),
    ('Black Pomfret', 'SMALL', '250-450 gms', 'Whole fish cleaned and gutted', '', 'Sea Water Fish', 360),
    ('Black Pomfret', 'Medium', '500 gms - 1kg', 'Curry cut with head', '', 'Sea Water Fish', 460),
    ('Black Pomfret', 'LARGE', '1-2kg', 'Curry cut with head', '', 'Sea Water Fish', 560),
    ('Lady fish/Kaane', 'SMALL', '10-25 pcs', 'Whole cleaned', '', 'Sea Water Fish', 320),
    ('Lady fish/Kaane', 'Medium', '5-10 pcs', 'Whole cleaned', '', 'Sea Water Fish', 400),
    ('Lady fish/Kaane', 'LARGE', '3-4 pcs', 'Whole cleaned', '', 'Sea Water Fish', 490),
    ('SQUID', '-', '5-15 PCS/kg', 'Rings', '1-4', 'Squid', 440),
    ('SQUID', '-', '5-15 PCS/kg', 'Whole', '1-4', 'Squid', 420),
    ('Sankra/Pink Perch', 'Medium', '6-13 pcs/kg', 'Whole cleaned', '1-4', 'Sea Water Fish', 440),
    ('Sankra/Pink Perch', 'LARGE', '4-6 Pcs/kg', 'Whole cleaned', '1-2', 'Sea Water Fish', 530),
    ('Mahi Mahi', '-', '1-6kg', 'Boneless cube', '', 'Sea Water Fish', 400),
    ('Red Snapper/Kemberi', '-', '3-6kg', 'Curry Cut', '', 'Sea Water Fish', 360),
    ('Red Snapper/Kemberi', '-', '3-6kg', 'Steaks', '', 'Sea Water Fish', 380),
    ('Red Snapper/Kemberi', '-', '3-6kg', 'Boneless cube', '', 'Sea Water Fish', 430),
    ('Bombay Duck', '-', '7-12 pcs/kg', 'Whole cleaned and gutted', '1-3', 'Sea Water Fish', 360),
    ('Nang/Sole fish', 'SMALL', '6-8 pcs/kg', 'Whole cleaned with head', '1-2', 'Sea Water Fish', 370),
    ('Nang/Sole fish', 'Medium', '4-6 pcs /kg', 'Whole cleaned with head', '1-2', 'Sea Water Fish', 450),
    ('Nang/Sole fish', 'LARGE', '3-4 pcs/kg', 'Whole cleaned with head', '0-1', 'Sea Water Fish', 470),
    ('Kandai-Barracuda', 'SMALL', '0.5-1kg', 'Steaks', '', 'Sea Water Fish', 380),
    ('Kandai-Barracuda', 'Medium', '1-2kg', 'Steaks', '', 'Sea Water Fish', 460),
    ('Kandai-Barracuda', 'LARGE', '2-3kg', 'Steaks', '', 'Sea Water Fish', 540),
    ('Trevally/Kokkar/Para', 'SMALL', '250-500gms', 'Steaks', '', 'Sea Water Fish', 400),
    ('Trevally/Kokkar/Para', 'SMALL', '250-500gms', 'Curry cut with head', '', 'Sea Water Fish', 400),
    ('Trevally/Kokkar/Para', 'Medium', '0.5-1kg', 'Steaks', '', 'Sea Water Fish', 500),
    ('Trevally/Kokkar/Para', 'Medium', '0.5-1kg', 'Curry cut with head', '', 'Sea Water Fish', 420),
    ('Trevally/Kokkar/Para', 'LARGE', '1-3kg', 'Steaks', '', 'Sea Water Fish', 520),
    ('Trevally/Kokkar/Para', 'LARGE', '1-3kg', 'Curry cut with head', '', 'Sea Water Fish', 520),
    ('Emperor', 'SMALL', '150-350GMS', 'Whole cleaned with head', '', 'Sea Water Fish', 350),
    ('Emperor', 'SMALL', '150-350GMS', 'Steaks', '', 'Sea Water Fish', 400),
    ('Emperor', 'Medium', '350-500GMS', 'Whole cleaned with head', '', 'Sea Water Fish', 440),
    ('Emperor', 'Medium', '350-500GMS', 'Steaks', '', 'Sea Water Fish', 500),
    ('Emperor', 'LARGE', '0.5-1KG', 'Whole cleaned with head', '', 'Sea Water Fish', 470),
    ('Emperor', 'LARGE', '0.5-1KG', 'Steaks', '', 'Sea Water Fish', 520),
    ('Tiger Prawns', '-', '12-20pcskg', 'Cleaned and deveined', '3-5', 'Prawns', 520),
    ('Atlantic salmon', '-', '2-3kg', 'Steaks', '', 'Sea Water Fish', 400),
    ('Atlantic salmon', '-', '2-3kg', 'Fillets', '', 'Sea Water Fish', 430),
    ('Atlantic salmon', '-', '2-3kg', 'Curry cut with head', '', 'Sea Water Fish', 400),
    ('3 Spotted Crab', '-', '3-12 pcs/kg', 'Whole cleaned', '0-3', 'Crabs', 580),
    ('Blue crab', '-', '3-5 pcs', 'Whole cleaned', '', 'Crabs', 520),
    ('Red Crab', '-', '3-5 pcs', 'Whole cleaned', '', 'Crabs', 530),
    ('Muru Fish', 'SMALL', '6-7 pcs /kg', 'Whole cleaned without skin', '1-2', 'Sea Water Fish', 340),
    ('Muru Fish', 'Medium', '3-5 pcs/kg', 'Whole cleaned without skin', '0-2', 'Sea Water Fish', 420),
    ('Muru Fish', 'LARGE', '1-2 pcs/kg', 'Whole cleaned without skin', '0-1', 'Sea Water Fish', 510),
    ('Disco', 'Medium', '4-5 pcs/kg', 'Whole cleaned without skin', '1-2', 'Sea Water Fish', 440),
    ('Disco', 'LARGE', '2-3 pcs/kg', 'Whole cleaned without skin', '0-1', 'Sea Water Fish', 530),
    ('Grey mullet', '-', '300-400gms', 'Whole cleaned', '', 'Sea Water Fish', 320),
    ('Mud crab', 'SMALL', '5-10pcs/kg', 'Whole cleaned', '1-3', 'Crabs', 530),
    ('Mud crab', 'Medium', '3-5pcs /kg', 'Whole cleaned', '0-2', 'Crabs', 610),
    ('Mud crab', 'LARGE', '0.600-2kg', 'Whole cleaned', '', 'Crabs', 700),
    ('Marwai/Shells', '-', '-', '-', '', 'Shells', 340),
]


def seed_products():
    create_db_and_tables()

    with Session(engine) as session:
        existing = session.exec(select(Product)).all()
        if existing:
            print(f"Database already contains {len(existing)} products. Skipping seed.")
            return

        products = []
        for name, size, fish_size, cut, pieces, category, price in MENU_ROWS:
            products.append(
                Product(
                    name=name,
                    category=category,
                    size=size,
                    fish_size=fish_size,
                    cut=cut,
                    pieces=pieces,
                    price=price,
                    image=None,
                    is_active=True,
                )
            )

        session.add_all(products)
        session.commit()
        print(f"Successfully inserted {len(products)} products.")


if __name__ == "__main__":
    seed_products()
