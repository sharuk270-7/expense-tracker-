"""
Configuration file for Expense Tracker Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_TOKEN")

# Database
DATABASE_PATH = "expenses.db"

# Supported categories
EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Entertainment",
    "Shopping",
    "Utilities",
    "Health",
    "Education",
    "Travel",
    "Work",
    "Meat",
    "Vegetables",
    "Fruits",
    "Hot Drinks",
    "Other"
]

# Currency
CURRENCY = "₹"

# Text patterns for expense detection
EXPENSE_PATTERNS = {
    "food": [
        "food", "eat", "meal", "snack", "breakfast", "brunch", "lunch", "dinner", "supper",
        "appetizer", "main course", "dessert", "bakery", "fast food", "street food",
        "aappam", "adai", "alfredo", "aloo paratha", "apple pie", "avocado toast",
        "bagel", "bacon", "biryani", "biriyani", "burger", "burrito", "broth", "brownie",
        "cake", "candy", "chapati", "chappathi", "chutney", "chowmein", "croissant", "cutlet",
        "dal", "dhokla", "dosa", "donut", "doughnut", "dumpling",
        "egg", "enchilada", "eclair", "edamame",
        "falafel", "fish fry", "fries", "fried rice", "focaccia",
        "garlic bread", "gnocchi", "gravy", "gulab jamun",
        "haleem", "hamburger", "hotdog", "hummus", "hyderabadi biryani",
        "idli", "ice cream", "imarti",
        "jalebi", "jam", "jowar roti",
        "kebab", "kebap", "kheer", "khichdi", "korma", "kulcha",
        "laddoo", "lasagna", "lemon rice", "lollipop chicken",
        "maggi", "manchurian", "momo", "muffin", "milkshake",
        "naan", "nachos", "noodles", "nuggets",
        "oats", "omelette", "omelet", "onion rings",
        "paneer", "pancake", "paratha", "pasta", "pizza", "poori", "puri", "pulao",
        "quesadilla", "quiche", "quinoa",
        "ramen", "rasam", "ravioli", "rice", "roti",
        "salad", "sandwich", "samosa", "soup", "spaghetti", "sushi",
        "taco", "tandoori", "thali", "tikka", "toast",
        "udon", "upma", "uttapam",
        "vada", "veg roll", "vermicelli",
        "waffle", "wrap", "wheat dosa",
        "xacuti",
        "yakhni", "yogurt", "yoghurt",
        "ziti", "zucchini fry"
    ],
    "transport": [
        "transport", "travel", "commute", "fare", "ride", "trip",
        "taxi", "cab", "uber", "ola", "rapido", "auto", "autorickshaw", "rickshaw",
        "bus", "metro", "subway", "tram", "train", "local train", "ticket", "pass",
        "flight", "airport transfer", "ferry", "boat",
        "bike", "bike taxi", "scooter", "cycle", "car", "parking", "toll",
        "fuel", "petrol", "diesel", "cng", "ev charging", "charging",
        "service", "maintenance", "puncture", "tyre"
    ],
    "entertainment": [
        "entertainment", "fun", "leisure", "outing", "party",
        "movie", "cinema", "film", "theatre", "show", "concert", "play", "standup", "comedy",
        "game", "gaming", "arcade", "bowling", "pool", "snooker",
        "netflix", "prime video", "hotstar", "spotify", "youtube premium", "subscription",
        "amusement park", "water park", "zoo", "museum", "event", "ticket", "festival"
    ],
    "shopping": [
        "shopping", "shop", "buy", "purchase", "order", "cart", "mall", "store",
        "clothes", "dress", "shirt", "tshirt", "jeans", "jacket", "shoe", "sneakers", "sandals",
        "bag", "wallet", "watch", "perfume", "cosmetics", "makeup", "accessories", "jewellery",
        "gift", "toys", "home decor", "furniture", "appliance", "electronics", "mobile", "laptop",
        "amazon", "flipkart", "myntra", "ajio", "zara", "h&m", "ikea"
    ],
    "utilities": [
        "utilities", "bill", "electricity", "power", "current", "water", "sewage",
        "internet", "wifi", "broadband", "phone", "mobile recharge", "postpaid", "prepaid",
        "gas", "lpg", "cylinder", "maintenance", "society maintenance",
        "rent", "house rent", "waste", "garbage", "dth", "cable", "subscription bill"
    ],
    "health": [
        "health", "medical", "medicine", "tablet", "syrup", "pharmacy", "chemist",
        "doctor", "clinic", "hospital", "lab", "scan", "xray", "mri", "blood test",
        "dental", "dentist", "eye", "optical", "checkup", "consultation", "therapy",
        "surgery", "emergency", "insurance", "health insurance", "first aid", "vitamin", "supplement"
    ],
    "education": [
        "education", "study", "course", "class", "tuition", "coaching", "training", "workshop",
        "book", "notebook", "stationery", "pen", "exam", "test", "assignment", "project work",
        "school", "college", "university", "certificate", "degree", "internship",
        "udemy", "coursera", "edx", "byjus", "unacademy", "skillshare"
    ],
    "travel": [
        "travel", "tour", "vacation", "holiday", "trip", "stay", "hotel", "resort", "hostel",
        "flight", "airfare", "train booking", "bus booking", "cab booking",
        "visa", "passport", "tour package", "itinerary", "sightseeing", "guide",
        "booking", "checkin", "checkout", "luggage", "homestay", "airbnb"
    ],
    "work": [
        "work", "office", "project", "meeting", "client", "business",
        "coworking", "workspace", "domain", "hosting", "software", "saas",
        "license", "printer", "ink", "paper", "stationery", "courier", "post",
        "laptop repair", "office supplies", "conference", "presentation"
    ],
    "meat": [
        "meat", "chicken", "fish", "beef", "pork", "mutton", "lamb", "steak",
        "goat", "turkey", "duck", "bacon", "ham", "sausage", "mince", "keema",
        "seafood", "prawn", "shrimp", "crab", "squid", "salmon", "tuna", "sardine"
    ],
    "vegetables": [
        "vegetable", "vegetables", "veggie", "veggies",
        "broccoli", "carrot", "spinach", "tomato", "onion", "potato", "cabbage",
        "cauliflower", "beetroot", "radish", "capsicum", "bell pepper", "lettuce",
        "cucumber", "pumpkin", "bottle gourd", "ridge gourd", "bitter gourd", "drumstick",
        "brinjal", "eggplant", "okra", "lady finger", "peas", "beans", "corn", "zucchini",
        "celery", "mushroom", "ginger", "garlic", "green chilli", "coriander", "mint",
        "ash gourd", "snake gourd", "ivy gourd", "cluster beans", "french beans", "broad beans",
        "spring onion", "shallots", "leek", "scallion", "turnip", "sweet potato", "yam", "colocasia",
        "taro", "raw banana", "plantain", "green banana", "raw papaya", "pointed gourd", "parwal",
        "chayote", "kohlrabi", "bok choy", "pak choi", "mustard greens", "fenugreek", "amaranth",
        "curry leaves", "dill", "parsley", "asparagus", "artichoke", "fennel", "kale",
        "microgreens", "watercress", "bean sprouts", "sprouts", "cherry tomato", "baby corn",
        "jalapeno", "red chilli", "yellow bell pepper", "green bell pepper", "purple cabbage",
        "red cabbage", "white radish", "daikon", "edamame", "green peas", "sweet corn",
        "cassava", "celeriac", "lotus stem", "banana stem", "banana flower", "moringa"
    ],
    "fruits": [
        "fruit", "fruits",
        "apple", "apricot", "avocado", "aonla",
        "banana", "ber", "blackberry", "blackcurrant", "blueberry", "boysenberry",
        "cantaloupe", "cherry", "clementine", "coconut", "cranberry", "currant", "custard apple",
        "date", "dates", "dragon fruit", "durian",
        "elderberry",
        "fig", "finger lime",
        "gooseberry", "grape", "grapes", "grapefruit", "guava",
        "honeydew",
        "indian plum",
        "jackfruit", "jamun", "java plum", "jujube",
        "kiwi", "kumquat",
        "lemon", "lime", "lychee", "litchi", "longan", "loquat",
        "mandarin", "mango", "mangosteen", "melon", "muskmelon", "mulberry",
        "nectarine",
        "olive", "orange",
        "papaya", "passion fruit", "peach", "pear", "persimmon", "pineapple", "plum", "pomelo", "pomegranate",
        "quince",
        "rambutan", "raspberry", "red banana", "rose apple",
        "sapota", "chikoo", "soursop", "star fruit", "strawberry", "sweet lime",
        "tangerine", "tender coconut",
        "ugli fruit",
        "velvet apple",
        "watermelon", "wood apple",
        "xigua",
        "yellow passion fruit",
        "zucchini fruit"
    ],
    "hot drinks": [
        "hot drink", "hot drinks",
        "coffee", "tea", "cappuccino", "latte", "espresso", "americano", "mocha", "macchiato",
        "filter coffee", "black coffee", "green tea", "masala tea", "chai", "ginger tea", "lemon tea",
        "hot chocolate", "milk", "badam milk", "horlicks", "boost", "soup",
        "turmeric milk", "haldi milk", "kashaya", "herbal tea", "black tea", "milk tea",
        "oolong tea", "white tea", "earl grey", "darjeeling tea", "assam tea", "matcha",
        "kasaya", "kadha", "kahwa", "sulaimani", "green coffee", "decaf coffee",
        "irish coffee", "affogato", "flat white", "ristretto", "cortado", "piccolo",
        "hot latte", "hot mocha", "milo", "bournvita", "malt drink", "hot bournvita",
        "tomato soup", "sweet corn soup", "mushroom soup", "veg soup", "chicken soup", "broth"
    ]
}
