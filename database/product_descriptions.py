"""Short preparation descriptions for the built-in cafe menu."""

PRODUCT_DESCRIPTIONS = {
    "Espresso": "A fresh double shot pulled from finely ground coffee beans.",
    "Americano": "Fresh espresso topped with hot water for a smooth, bold coffee.",
    "Cappuccino": "Espresso finished with steamed milk and a thick layer of milk foam.",
    "Caffe Latte": "Espresso combined with steamed milk and a light layer of foam.",
    "Caffe Mocha": "Espresso blended with chocolate and steamed milk.",
    "Iced Coffee": "Chilled coffee poured over ice and finished with milk.",
    "Hot Chocolate": "Chocolate mixed into steamed milk and served warm.",
    "Croissant": "Buttery layered pastry baked until golden and crisp.",
    "Blueberry Muffin": "Soft muffin batter baked with sweet blueberries.",
    "Chocolate Chip Cookie": "Cookie dough baked with chocolate chips until golden.",
    "Cheesecake Slice": "Creamy cheesecake baked on a crumb crust and served by the slice.",
    "Ham & Cheese Sandwich": "Ham and cheese layered in bread, then toasted until warm.",
    "Tuna Sandwich": "Seasoned tuna filling layered with fresh greens in soft bread.",
    "Caesar Salad": "Crisp lettuce tossed with Caesar dressing, croutons, and cheese.",
    "Bottled Water": "Sealed bottled water served chilled.",
    "Iced Tea": "Brewed tea chilled and served over ice.",
}

CATEGORY_DESCRIPTIONS = {
    "Coffee Drinks": "Freshly prepared with espresso or brewed coffee and served as ordered.",
    "Freshie Drinks": "Prepared or chilled and served fresh for a refreshing drink.",
    "Meals": "Assembled fresh to order using the cafe's standard recipe.",
    "Pastry": "Baked until ready to serve and offered fresh from the pastry selection.",
}


def default_product_description(name, category):
    return PRODUCT_DESCRIPTIONS.get(name, CATEGORY_DESCRIPTIONS.get(
        category, "Prepared to order using the cafe's standard recipe."
    ))
