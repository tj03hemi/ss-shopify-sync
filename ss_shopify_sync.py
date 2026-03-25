"""
Summit Standard Co. — S&S Activewear to Shopify Sync
=====================================================
Clean, reliable build. Key design decisions:
- Explicit style list per category (no guessing)
- Large variant products split into color groups
- Retry logic on Shopify API failures
- Active products never demoted to draft
- Shopify category set via GraphQL on creation
"""
import os, requests, base64, time, json
from datetime import datetime

# ── Credentials ───────────────────────────────────────────────
SS_USERNAME          = os.environ.get("SS_USERNAME", "")
SS_API_KEY           = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE        = os.environ.get("SHOPIFY_STORE", "")
SHOPIFY_CLIENT_ID    = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET= os.environ.get("SHOPIFY_CLIENT_SECRET", "")

SS_BASE = "https://api.ssactivewear.com/v2"
SS_IMG  = "https://www.ssactivewear.com/"

# Max variants per Shopify product — Shopify times out above ~150
MAX_VARIANTS = 100

# ── Explicit style list ───────────────────────────────────────
# Format: (brand, style_name, collection_handle, category_tag, taxonomy_gid)
# Using BrandName + StyleName which S&S confirmed works
STYLES = [
# ── HATS ──
    ("Richardson", "110", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # R-Flex Trucker Cap
    ("Richardson", "111", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Garment-Washed Trucker Cap
    ("Richardson", "111P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Garment Washed Printed Trucker Cap
    ("Richardson", "112", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Snapback Trucker Cap
    ("Richardson", "112FP", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Trucker Cap
    ("Richardson", "112FPC", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Champ Trucker Cap
    ("Richardson", "112FPR", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Trucker Rope Cap
    ("Richardson", "112P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Printed Trucker Cap
    ("Richardson", "112PL", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # 112+ R-Flex Adjustable Trucker Cap
    ("Richardson", "112PM", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Printed Mesh Trucker Cap
    ("Richardson", "112RE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Sustainable Trucker Cap
    ("Richardson", "112T", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Tactical Trucker Cap
    ("Richardson", "112WF", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Fremont Trucker Cap
    ("Richardson", "112Y", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Youth Trucker Snapback Cap
    ("Richardson", "113", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Foamie Trucker Cap
    ("Richardson", "115", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Low Pro Trucker Cap
    ("Richardson", "168", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Seven-Panel Trucker Cap
    ("Richardson", "212", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Pro Twill Snapback Cap
    ("Richardson", "213", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Low-Pro Foamie Trucker Cap
    ("Richardson", "220", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Relaxed Performance Lite Cap
    ("Richardson", "225", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Casual Performance Lite Cap
    ("Richardson", "253", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Timberline Corduroy Cap
    ("Richardson", "254RE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Ashland Dad Hat
    ("Richardson", "255", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Pinch Front Structured Snapback Trucker Cap
    ("Richardson", "256", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Umpqua Gramps Cap
    ("Richardson", "258", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Classic Rope Cap
    ("Richardson", "312", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Twill Back Trucker Cap
    ("Richardson", "326", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Peach Twill Dad Hat
    ("Richardson", "336", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Burnside Cap
    ("Richardson", "356", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Gramps Cap
    ("Richardson", "511", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Wool Blend Flat Bill Trucker Cap
    ("Richardson", "512", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Surge Snapback Cap
    ("Richardson", "514", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Surge Adjustable Cap
    ("Richardson", "632", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Laser Perf R-Flex Cap
    ("Richardson", "835", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Tilikum Cap
    ("Richardson", "909", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # McKenzie Booney
    ("Richardson", "930", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Troutdale Corduroy Trucker Cap
    ("Richardson", "935", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Rogue Wide Set Mesh Cap
    ("Flexfit", "110C", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 110 Pro-Formance Cap
    ("Flexfit", "110F", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # 110 Snapback Cap
    ("Flexfit", "110M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # 110 Mesh-Back Cap
    ("Flexfit", "110P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 110 Cool Dry Mini-Pique Cap
    ("Flexfit", "110R", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # 110 Recycled Mesh Cap
    ("Flexfit", "180", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Delta Seamless Cap
    ("Flexfit", "180AP", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Delta Snapback Perforated Cap
    ("Flexfit", "280", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Delta Seamless Unipanel Cap
    ("Flexfit", "5001", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # V-Flexfit Cotton Twill Cap
    ("Flexfit", "5511UP", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Unipanel Trucker Cap
    ("Flexfit", "5577UP", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Unipanel Melange Cap
    ("Flexfit", "6100NU", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # NU Cap
    ("Flexfit", "6110NU", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # NU Adjustable Cap
    ("Flexfit", "6210FF", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # 210 Flat Bill Cap
    ("Flexfit", "6277", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Cotton Blend Cap
    ("Flexfit", "6277R", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Polyester Cap
    ("Flexfit", "6277Y", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Youth Cotton Blend Cap
    ("Flexfit", "6297F", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Pro-Baseball On Field Cap
    ("Flexfit", "6311", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Melange Trucker Cap
    ("Flexfit", "6350", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Heatherlight Melange Cap
    ("Flexfit", "6477", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Wool-Blend Cap
    ("Flexfit", "6511", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Trucker Cap
    ("Flexfit", "6533", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Ultrafiber Mesh Cap
    ("Flexfit", "6577CD", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Cool Dry Pique Mesh Cap
    ("Flexfit", "6580", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Pro-Formance Cap
    ("Flexfit", "6597", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Cool Dry Sport Cap
    ("Flexfit", "8110", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 110 Visor
    ("Sportsman", "SP03", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 8in Marled Beanie
    ("Sportsman", "SP08", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 8in Beanie
    ("Sportsman", "SP09", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 8in Bottom-Striped Beanie
    ("Sportsman", "SP12", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 12in Solid Cuffed Beanie
    ("Sportsman", "SP12FL", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 12in Fleece Lined Cuffed Beanie
    ("Sportsman", "SP12SL", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 12in Sherpa Lined Cuffed Beanie
    ("Sportsman", "SP12T", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 12in Color Blocked Cuffed Beanie
    ("Sportsman", "SP1200", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Ripstop Cap
    ("Sportsman", "SP1300", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Rope Heritage Fit Cap
    ("Sportsman", "SP1400", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Lo-Pro Solid Traditional Cap
    ("Sportsman", "SP1450", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Traditional Lo-Pro Mesh Back Trucker Fit Cap
    ("Sportsman", "SP15", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 12in Pom-Pom Cuffed Beanie
    ("Sportsman", "SP1550", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Modern Five-Panel Trucker Fit Cap
    ("Sportsman", "SP1650", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Modern Six-Panel Trucker Fit Cap
    ("Sportsman", "SP1700", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Dad Hat Fit
    ("Sportsman", "SP1750", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Mesh Dad Hat Fit
    ("Sportsman", "SP60", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 12in Striped Pom-Pom Cuffed Beanie
    ("Sportsman", "SP90", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 12in Chunky Cuffed Beanie
    ("YP Classics", "1500KC", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # 8.5in Beanie
    ("YP Classics", "1501KC", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Cuffed Beanie
    ("YP Classics", "1501P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Pom-Pom Cuffed Knit Beanie
    ("YP Classics", "2501KC", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Waffle Cuffed Knit Beanie
    ("YP Classics", "5079", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Retro Cotton Blend Snapback Cap
    ("YP Classics", "5089M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Premium Five-Panel Snapback Cap
    ("YP Classics", "5389AP", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Snapback with Perforated Cap
    ("YP Classics", "5789M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Premium Five-Panel Curved Bill Snapback Cap
    ("YP Classics", "6002YP", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Classic Poplin Golf Cap
    ("YP Classics", "6006", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Classic Five-Panel Trucker Cap
    ("YP Classics", "6007", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Cotton Twill Snapback Cap
    ("YP Classics", "6089M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Premium Flat Bill Snapback Cap
    ("YP Classics", "6245CM", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Classic Dad Hat
    ("YP Classics", "6245EC", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # EcoWash Dad Hat
    ("YP Classics", "6245PT", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Peached Cotton Twill Dad Hat
    ("YP Classics", "6363V", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Structured Brushed Twill Cap
    ("YP Classics", "6389", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # CVC Snapback Cap
    ("YP Classics", "6502", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Lightly-Structured Five-Panel Snapback Cap
    ("YP Classics", "6506", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Retro Trucker Cap
    ("YP Classics", "6601", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Elite Cap
    ("YP Classics", "6606", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Retro Trucker Cap
    ("YP Classics", "6606R", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Sustainable Retro Trucker Cap
    ("YP Classics", "6609", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Retro High Profile Trucker Cap
    ("YP Classics", "6789M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Premium Curved Bill Snapback Cap
    ("YP Classics", "7005", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Classic Jockey Flat Bill Cap
    ("Imperial", "1287", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # North Country Trucker Cap
    ("Imperial", "1371P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # The Oxford Performance Bucket Hat
    ("Imperial", "1988M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # The Whitaker Mesh Cap
    ("Imperial", "3124P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Performance Phoenix Visor
    ("Imperial", "4072", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Easy Read Cap
    ("Imperial", "4074", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Passenger Side Cap
    ("Imperial", "5054", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Wrightson Cap
    ("Imperial", "5054U", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Harrison Cap
    ("Imperial", "5055", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Rabble Rouser Cap
    ("Imperial", "5056", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Barnes Cap
    ("Imperial", "5058", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Outtasite Cap
    ("Imperial", "6054", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Habanero Performance Rope Cap
    ("Imperial", "7054", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Wingman Cap
    ("Imperial", "7054N", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Independent Cap
    ("Imperial", "7055", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Night Owl Performance Rope Cap
    ("Imperial", "DNA001", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # The Original Rope Five-Panel Cap
    ("Imperial", "DNA010", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Aloha Rope Cap
    ("Imperial", "DNA014", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Golden Hour Cap
    ("Imperial", "L210P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Original Small Fit Performance Cap
    ("Imperial", "L338", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Hinsen Performance Ponytail Cap
    ("Imperial", "L338M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # The Hinsen Mesh Back Cap
    ("Imperial", "L5059", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Corral Cap
    ("Imperial", "S1502", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Alpha Cap
    ("Imperial", "S1505", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Dyno Cap
    ("Imperial", "X210B", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Original Buckle Dad Hat
    ("Imperial", "X210P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Original Performance Cap
    ("Imperial", "X210R", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Alter Ego Cap
    ("Imperial", "X210SM", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # The Original Sport Mesh Cap
    ("Imperial", "X210X", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Sophisticate Cap
    ("Imperial", "X240", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Gambit Cap
    ("Imperial", "X240M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # The Gambit Mesh Back Cap
    ("The Game", "GB210", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Classic Twill Cap
    ("The Game", "GB400", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Ultralight Booney
    ("The Game", "GB452E", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Everyday Trucker Cap
    ("The Game", "GB452R", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Everyday Rope Trucker Cap
    ("The Game", "GB460", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Pigment-Dyed Trucker Cap
    ("The Game", "GB465", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Pigment-Dyed Cap
    ("The Game", "GB510", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Ultralight Cotton Twill Cap
    ("The Game", "GB880", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Soft Trucker Cap
    ("LEGACY", "B9A", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Back Nine Cap
    ("LEGACY", "CADDY", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Caddy Rope Adjustable Cap
    ("LEGACY", "CFA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Cool Fit Adjustable Cap
    ("LEGACY", "CFB", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Cool Fit Booney
    ("LEGACY", "CHILL", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Chill Cap
    ("LEGACY", "CUT", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # The Cut Above Cap
    ("LEGACY", "DTA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Dashboard Trucker Cap
    ("LEGACY", "EZA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Relaxed Twill Dad Hat
    ("LEGACY", "HTA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Heritage Twill Cap
    ("LEGACY", "LPS", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Lo-Pro Snapback Trucker Cap
    ("LEGACY", "LTA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Laguna Cap
    ("LEGACY", "MPS", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Mid-Pro Snapback Trucker Cap
    ("LEGACY", "OFA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Old Favorite Trucker Cap
    ("LEGACY", "OFAFP", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Old Favorite Five-Panel Trucker Cap
    ("LEGACY", "OFAST", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Old Favorite Solid Twill Cap
    ("LEGACY", "OFAY", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Youth Old Favorite Trucker Cap
    ("LEGACY", "RECS", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Reclaim Sport Mesh Cap
    ("LEGACY", "ROADIE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Adjustable Cap
    ("LEGACY", "SKULLY", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Skully Rope Cap
    ("LEGACY", "TTA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Terra Twill Cap
    ("Outdoor Cap", "CARG100", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Cargo Cap with pockets
    ("Outdoor Cap", "OC771", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Modern Trucker Cap
    ("Outdoor Cap", "OC870", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Knit Beanie
    ("Outdoor Cap", "OCHPD610M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Weathered Mesh-Back Cap
    ("Outdoor Cap", "OCSAF201", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Reflective Cap
    ("Outdoor Cap", "ODC771", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Trucker Cap
    ("Outdoor Cap", "PN100", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Solid Back Cap
    ("Top of the World", "5505", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Ranger Cap
    ("Top of the World", "5528", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Ballaholla Cap
    ("CAP AMERICA", "i1002", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Relaxed Golf Dad Hat
    ("CAP AMERICA", "i7007", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Soft Fit Active Wear Cap
    ("CAP AMERICA", "i7023", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Structured Active Wear Cap
    ("CAP AMERICA", "i7256", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Athletic Rope Cap
    ("CAP AMERICA", "i8522", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Premium Athletic Cap
    ("CAP AMERICA", "i8540", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Premium Water-Resistant Perforated Cap
    ("CAP AMERICA", "x800", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # X-tra Value Polyester Trucker Cap
    ("47 Brand", "4700", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Clean Up Cap
    ("47 Brand", "4710", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Trawler Cap
    ("Adams Headwear", "ED101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Endurance Recycled Mesh Cap
    ("Adams Headwear", "LP101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Optimum Pigment-Dyed Dad Hat
    ("Adams Headwear", "LP104", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Optimum II True Color Cap
    ("Adams Headwear", "LP107", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Icon Sandwich Cap
    ("Adams Headwear", "LP108", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Classic Pigment Distressed Cap
    ("Adams Headwear", "OL102", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Ollie Distressed Cap
    ("Adams Headwear", "PE102", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Performer Cap
    ("Adams Headwear", "PF101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Pro-Flow Cap
    ("Adams Headwear", "VA101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Vacationer Bucket Hat
    ("Adams Headwear", "VE101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Velocity Cap
    ("Adams Headwear", "XP101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Extreme Adventurer Bucket Hat
    ("Atlantis Headwear", "ANDY", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Fine Rib Cuffed Beanie
    ("Atlantis Headwear", "BRYCE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Sustainable Trucker Cap
    ("Atlantis Headwear", "FIJI", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Sustainable Five-Panel Cap
    ("Atlantis Headwear", "FRASER", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Dad Hat
    ("Atlantis Headwear", "GEO", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Sustainable Bucket Hat
    ("Atlantis Headwear", "HOLLY", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Beanie
    ("Atlantis Headwear", "JAMES", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Sustainable Flat Bill Cap
    ("Atlantis Headwear", "JOSHUA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Structured Cap
    ("Atlantis Headwear", "MAPLE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Finish Edge Cuffed Beanie
    ("Atlantis Headwear", "MOOVER", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable 8in Beanie
    ("Atlantis Headwear", "NELSON", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Cuffed Beanie
    ("Atlantis Headwear", "OAK", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Chunky Rib Cuffed Beanie
    ("Atlantis Headwear", "POWELL", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Sustainable Bucket Hat
    ("Atlantis Headwear", "PURE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Beanie
    ("Atlantis Headwear", "RAPPER", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Canvas Cap
    ("Atlantis Headwear", "REFE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Recy Feel Cap
    ("Atlantis Headwear", "RETH", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Sustainable Recy Three Trucker Cap
    ("Atlantis Headwear", "RIO", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Rib Cuffed Beanie
    ("Atlantis Headwear", "SAND", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Performance Cap
    ("Atlantis Headwear", "SHINE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Reflective Beanie
    ("Atlantis Headwear", "SHORE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Cable Knit Cuffed Beanie
    ("Atlantis Headwear", "SKYE", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Honeycomb Cap
    ("Atlantis Headwear", "WIND", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable 12in Knit Beanie
    ("Atlantis Headwear", "YALA", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Sustainable Beanie
    ("Atlantis Headwear", "ZION", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Sustainable Five-Panel Trucker Cap
    ("Valucap", "2050", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Bucket Hat
    ("Valucap", "2260", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Cotton Twill Cap
    ("Valucap", "2260Y", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Youth Small Fit Cotton Twill Cap
    ("Valucap", "3100", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Contrast-Stitch Mesh-Back Cap
    ("Valucap", "3150", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Bounty Dirty-Washed Mesh-Back Cap
    ("Valucap", "3200", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Spacer Mesh-Back Cap
    ("Valucap", "6440", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Econ Cap
    ("Valucap", "8804H", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Trucker Cap
    ("Valucap", "8869", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Five-Panel Twill Cap
    ("Valucap", "9610", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Heavy Brushed Twill Unstructured Cap
    ("Valucap", "9910", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Heavy Brushed Twill Structured Cap
    ("Valucap", "AH30", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Structured Cap
    ("Valucap", "AH35", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Unstructured Cap
    ("Valucap", "AH80", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Bio-Washed Trucker Cap
    ("Valucap", "S102", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Sandwich Trucker Cap
    ("Valucap", "SM140", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Performance Microfiber Cap
    ("Valucap", "SP500", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Pigment-Dyed Cap
    ("Valucap", "SP510", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Pigment-Dyed Trucker Cap
    ("Valucap", "VC100", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Lightweight Twill Cap
    ("Valucap", "VC150", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Licensed Camo Cap
    ("Valucap", "VC200", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Brushed Twill Cap
    ("Valucap", "VC300A", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Bio-Washed Classic Dad Hat
    ("Valucap", "VC300Y", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Youth Small Fit Bio-Washed Dad Hat
    ("Valucap", "VC350", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Bio-Washed Chino Twill Cap
    ("Valucap", "VC400", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Mesh-Back Twill Trucker Cap
    ("Valucap", "VC500", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Bio-Washed Visor
    ("Valucap", "VC600", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Chino Cap
    ("Valucap", "VC700", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Foam Mesh-Back Trucker Cap
    ("Valucap", "VC990", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Contrast Stitch Cap
    ("Pukka", "5000M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Rudder Five-Panel Cap
    ("Pukka", "6101M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Charter Six-Panel Cap
    ("Pukka", "7001P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),  # Tradesman Hybrid Six-Panel Cap

# ── POLOS ──
    ("Gildan", "64800", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Gildan", "64800L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Gildan", "85800", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Gildan", "8800", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Gildan", "8800B", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Hanes", "054X", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Hanes", "054Y", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Hanes", "055P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "436MP", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "436MPR", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "437F", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "437K", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "437LR", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "437MSR", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "437R", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "437WR", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "442M", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "443M", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "443W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES", "537MR", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "78181", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "78181P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "78181R", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "78192", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88181", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88181P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88181R", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88181T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88181Y", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88192", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88192P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "88192T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE101", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE101W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE104", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE104W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE106", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE106T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE106W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE106Y", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE108", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE108L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE108LW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE108P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE108T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE108W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE108Y", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE112", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE112C", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE112CW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE112L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE112T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE112W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE401", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE401W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE404", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE404W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE405", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE405W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE418", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365", "CE418W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M105", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M105T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M105W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M200", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M200T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M200W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M205", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M205P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M205W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M208", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M208L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M208W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M211", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M211L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M211LW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M211W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M265", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M265L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M265P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M265W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M280W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M315", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M315W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M345", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M345W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M348", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M348L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M348LT", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M348LW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M348P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M348T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M348W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M353W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M354", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M374W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M385", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M385W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M386", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M386W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M415", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M415W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M420", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M420W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M421", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M425", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M425W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M712", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M748", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M748W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Columbia", "177205", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Columbia", "211856", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Columbia", "212469", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Columbia", "212495", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Columbia", "213624", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "3350", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "1051", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "1060", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "1480", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "2231", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "4006", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "4102", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Badger", "4103", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT125", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT125W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT20W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT21", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT21C", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT21CW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT21W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT22W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51H", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51HW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51HY", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51LW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51T", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT51Y", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT200W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT31", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT31H", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT31HW", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT31HY", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT31W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Team 365", "TT31Y", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1370399", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1370431", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1376904", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1376905", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1376907", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1377374", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1377376", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1377377", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1378676", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1383255", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1383263", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1385910", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1389853", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1373674", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1376844", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1376862", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1383256", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1383259", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1383260", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1383272", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1383274", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1387124", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Under Armour", "1389864", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1005", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1008", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1016", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2004", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2005", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2008", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2012", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2013", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2014", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2015", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2023", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2024", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2026", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2028", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A213", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A230", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A231", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A324", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A325", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A402", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A403", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A430", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A431", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A480", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A481", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A490", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A498", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A508", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A512", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A514", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A515", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A550", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A574", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A580", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A581", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A582", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A583", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A584", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A585", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A590", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A591", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A592", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1002", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1003", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1007", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1011", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A1015", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2002", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2017", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A2020", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A295", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A400", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A401", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A475", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A476", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A482", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A483", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A520", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A521", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A522", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A532", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A552", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A554", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A555", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A587", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A588", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A589", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A593", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Adidas", "A594", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Devon & Jones", "DG150", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Devon & Jones", "DG150W", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),

# ── T-SHIRTS ──
    ("Gildan", "2000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "2000B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "2000L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "2200", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "2300", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "2400", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "3000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "3000B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "42000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "42000B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "42400", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5000B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5000L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5200", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5300", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5400", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5400B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5700", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "5V00L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64000B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64000CVC", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64000L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64200", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64200L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64400", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64V00", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "64V00L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "65000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "65000B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "65000L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "75000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "8000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "8000B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "8300", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "8400", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "880", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "980", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "H000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan", "H400", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "1510", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "1530", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "1533", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "1540", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "3310", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "3600", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "3601", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "3605", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "3900", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "3910", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "3940", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6010", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6200", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6210", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6240", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6410", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6600", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6610", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "6710", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "7200", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level", "7410", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "1717", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "1745", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "3023CL", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "4017", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "4410", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "6014", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "6030", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "9018", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors", "9360", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "4820", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "4980", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "498L", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5170", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5180", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5186", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5250", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5280", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5286", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5370", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5450", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5480", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5546", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5586", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5680", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "5780", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "SL04", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "S04V", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes", "W110", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Independent Trading Co.", "IND50TEE", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Independent Trading Co.", "PRM180LST", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Independent Trading Co.", "PRM180PT", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Independent Trading Co.", "SS150J", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH100", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH11B", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH125", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH150", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH175", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH200", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH280", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH300", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Lane Seven", "LS15000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Lane Seven", "LS15001", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Lane Seven", "LS15009", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Lane Seven", "LS16005", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Lane Seven", "LST002", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "1701", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "1715", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "1725", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "5000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "5025", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "5040", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "5100", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "5710", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Bayside", "9500", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "2616", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "3502", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "3507", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "3516", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "3520", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "3592", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "6101", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "6901", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("LAT", "6906", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "202", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "202LS", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "213", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "216", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "241", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "290", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "291", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "502", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Tultex", "602", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Champion", "CH1000", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Champion", "CH1081", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Champion", "CHP160", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Champion", "T105", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Champion", "T425", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Champion", "T453", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),

# ── SWEATSHIRTS & FLEECE ──
    ("Gildan", "18500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "18500B", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "18600", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "18600B", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "12500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "19500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "SF500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "SF500B", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "SF600", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "AFX90UN", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "AFX90UNZ", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "AFX64CRP", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "IND4000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "IND4000Z", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "IND5000P", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS1000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS1000Z", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS4500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS4500Z", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "PRM4500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "PRM4500TD", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "PRM2500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "PRM2500Z", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS4001Y", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS4001YZ", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "4997MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "700MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "90MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "993BR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "993MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "996MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "996YR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "96CR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "97CR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "98CR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "H12MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "IC49MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "Z12MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "S700", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "S760", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "S790", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "S800", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "CD450", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "CHP100", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "CHP180", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "S101", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "S171", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion", "RW01W", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "F170", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "F280", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "OG700", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "P170", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "P180", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "P473", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "P480", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Hanes", "RS170", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Russell Athletic", "695HBM", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Russell Athletic", "82ONSM", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan", "18000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Gildan", "18000B", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Gildan", "12000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Gildan", "18810", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Gildan", "19000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Gildan", "SF000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Gildan", "SF008", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Independent Trading Co.", "AFX24CRP", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Independent Trading Co.", "IND3000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Independent Trading Co.", "IND5000C", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Independent Trading Co.", "SS1000C", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Independent Trading Co.", "SS3000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Independent Trading Co.", "PRM3500", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Independent Trading Co.", "PRM2000", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "4662MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "4528MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "562MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "562BR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "701MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "91MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "995MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "C12MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "IC48MR", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Champion", "S149", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Champion", "S600", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Champion", "SL650", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Champion", "CD400D", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Champion", "CHP190", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Champion", "S450", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Hanes", "F260", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Hanes", "OG600", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Hanes", "OG900", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Hanes", "P160", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Hanes", "P360", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Hanes", "RS160", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Columbia", "212475", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Columbia", "212487", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Columbia", "216515", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Russell Athletic", "698HBM", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Russell Athletic", "1Z4HBM", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Russell Athletic", "R03GKM", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),

# ── JACKETS & OUTERWEAR ──
    ("Columbia", "155653", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "179975", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "205472", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "207134", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "208499", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "208624", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "208687", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "208827", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "208855", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "208903", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "208934", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "208959", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209002", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209029", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209573", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209574", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209575", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "209578", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209647", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209769", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "209926", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "209927", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "211390", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "211592", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "211658", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "211667", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212106", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212371", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212428", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212470", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212471", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "212476", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212478", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212479", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212480", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212481", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212483", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212486", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212488", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "212489", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212490", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212491", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "212492", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "212493", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "212494", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "213430", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "213684", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "216509", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia", "216510", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Columbia", "217748", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "78032", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "78034", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "78166", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "78174", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "78178", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "78196", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "78697", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88006", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88007", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88083", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88099", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88130", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88138", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88159", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88166", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88172", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88174", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88178", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88196", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "88697", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE708", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE708W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE714", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("North End", "NE714W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("North End", "NE721", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE722", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE730", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE730W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE731", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("North End", "NE731W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("North End", "NE75", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE75W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE810", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End", "NE810W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M705", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M72", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M721", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M721T", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M722", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M722T", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M723", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Harriton", "M73", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton", "M740", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5020", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5020T", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5028", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5028T", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5032", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5033", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5034", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5037", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5057", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5066", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5068", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("DRI DUCK", "5089", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5090", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5091", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5301", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("DRI DUCK", "5302", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5303", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5304", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5310", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5316", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5318", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("DRI DUCK", "5323", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5324", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5325", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5326", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5327", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5328", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5330", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5335", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5339", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5350", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "5365", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7033", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7040", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7340", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7348", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7349", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7352", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7353", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK", "7355", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "15600", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "15600W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "16700", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Weatherproof", "16700W", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Weatherproof", "193910", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "207359", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Weatherproof", "211136", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "211137", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "21752", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "26714", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Weatherproof", "26715", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "26717", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Weatherproof", "6500", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "W207359", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Weatherproof", "W21752", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "W26715", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "W26717", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Weatherproof", "W26719", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof", "W6500", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A1009", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A1012", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A2007", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A2016", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A2027", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A267", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A268", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A570", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas", "A572", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Adidas", "A573", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Under Armour", "1359348", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1359386", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1371585", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1371586", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1371587", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1371594", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1374644", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1379806", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1379842", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1387024", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1387568", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1389182", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1389595", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Under Armour", "1389611", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1389661", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour", "1390159", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "187330", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "187333", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "187334", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "187335", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "187336", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "187337", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S16522", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S16523", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S16538", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S16539", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S16561", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S16562", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S16641", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S16642", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17028", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17029", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17030", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17274", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17275", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17298", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "s17299", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17302", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17388", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17740", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17741", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17742", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17743", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17749", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17907", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17918", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17919", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17920", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17921", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17929", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17930", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17931", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17932", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17936", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17937", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17940", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17965", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17977", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17978", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S17995", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17996", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S17999", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S18000", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),
    ("Spyder", "S18030", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S18031", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S18074", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder", "S18098", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),

# ── WOVEN & DRESS SHIRTS ──
    ("Harriton", "M500", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Harriton", "M500W", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Devon & Jones", "D620", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Devon & Jones", "DG535", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Red Kap", "SP24", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Red Kap", "SP14", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Red Kap", "SP84", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Dickies", "5574", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Dickies", "L307", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Columbia", "177205", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),

# TOTAL STYLES: 972

]

# ── S&S API ───────────────────────────────────────────────────
def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

def ss_get(path, params=None, retries=2):
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{SS_BASE}/{path}", headers=ss_auth(),
                             params=params, timeout=30)
            rem = int(r.headers.get("X-Rate-Limit-Remaining", 60))
            if rem < 5:
                print("    ⏳ S&S rate limit — pausing 5s")
                time.sleep(5)
            return r
        except requests.exceptions.Timeout:
            if attempt < retries:
                print(f"    ⚠️  S&S timeout, retry {attempt+1}/{retries}...")
                time.sleep(2)
            else:
                print("    ❌ S&S timeout after retries")
                return None
        except Exception as e:
            print(f"    ❌ S&S error: {e}")
            return None

def get_style(brand, style_name):
    """Fetch style using BrandName StyleName format."""
    identifier = f"{brand} {style_name}"
    enc = requests.utils.quote(identifier)
    r = ss_get(f"styles/{enc}")
    if r and r.status_code == 200:
        d = r.json()
        if isinstance(d, list) and d:
            return d[0]
    # Fallback: search
    r2 = ss_get("styles/", params={"search": f"{brand} {style_name}"})
    if r2 and r2.status_code == 200:
        d = r2.json()
        if isinstance(d, list) and d:
            # Find best match
            for s in d:
                if (s.get("brandName","").lower() == brand.lower() and
                    s.get("styleName","").lower() == style_name.lower()):
                    return s
            return d[0]
    return None

def get_products(style_id):
    """Get all SKUs for a style."""
    r = ss_get(f"products/?style={style_id}")
    if r and r.status_code == 200:
        data = r.json()
        return data if isinstance(data, list) else []
    return []

def get_specs(style_id):
    """Get garment specs for a style."""
    r = ss_get(f"specs/?style={style_id}")
    if r and r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            return [s for s in data if str(s.get("styleID","")) == str(style_id)]
    return []

def img_url(path):
    if not path: return None
    full = f"{SS_IMG}{path}" if not path.startswith("http") else path
    return full.replace("_fm.", "_fl.")

# ── Build Shopify product ─────────────────────────────────────
def build_specs_html(specs):
    if not specs: return ""
    seen = {}
    for s in specs:
        n, v = s.get("specName",""), s.get("value","")
        if n and n not in seen: seen[n] = v
    if not seen: return ""
    rows = "".join(f"<tr><td style='padding:4px 8px;'><strong>{k}</strong></td>"
                   f"<td style='padding:4px 8px;'>{v}</td></tr>"
                   for k,v in list(seen.items())[:15])
    return (f'<h4 style="margin-top:16px;">Specs</h4>'
            f'<table style="font-size:13px;width:100%;border-collapse:collapse;">'
            f'<tbody>{rows}</tbody></table>')

def build_product(style, products, specs, col_handle, cat_tag):
    brand    = style.get("brandName", "")
    sname    = style.get("styleName", "")
    title_s  = style.get("title", "")
    desc     = style.get("description", "")
    style_id = style.get("styleID", "")

    title = f"{brand} {sname} — {title_s}" if title_s else f"{brand} {sname}"

    # Group products by color to build variants + images
    color_groups = {}
    for p in products:
        color = p.get("colorName", "Default")
        if color not in color_groups:
            color_groups[color] = []
        color_groups[color].append(p)

    variants = []
    images   = []
    total    = 0

    for color, items in color_groups.items():
        if total >= MAX_VARIANTS:
            break
        first = items[0]
        # Get image for this color
        img_path = (first.get("colorOnModelFrontImage") or
                    first.get("colorFrontImage") or
                    first.get("colorSideImage") or "")
        url = img_url(img_path)
        if url:
            images.append({"src": url, "alt": f"{title} — {color}"})

        for p in items:
            if total >= MAX_VARIANTS:
                break
            variants.append({
                "option1": color,
                "option2": p.get("sizeName", "One Size"),
                "sku":     p.get("sku", ""),
                "price":   "0.00",
                "inventory_management": None,
                "fulfillment_service":  "manual",
                "requires_shipping":    True,
                "weight":      float(p.get("unitWeight", 0) or 0),
                "weight_unit": "lb",
            })
            total += 1

    if not variants:
        variants = [{"price": "0.00", "option1": "Default", "option2": "One Size"}]

    # Gender tag
    cats = str(style.get("categories",""))
    gender = "unisex"
    if "87" in cats.split(","): gender = "mens"
    elif "13" in cats.split(","): gender = "womens"
    elif "28" in cats.split(","): gender = "youth"

    safe_brand = brand.lower().replace(" ","-").replace("&","and").replace("+","plus")
    body = f"""<div>
<p>{desc}</p>
{build_specs_html(specs)}
<p style="margin-top:14px;font-size:13px;color:#555;">
<strong>Brand:</strong> {brand} &nbsp;|&nbsp;
<strong>Style:</strong> {sname} &nbsp;|&nbsp;
<strong>S&amp;S ID:</strong> {style_id}<br>
<em>Available for custom embroidery with your logo.
<a href="/pages/custom-orders">Request a quote →</a></em>
</p></div>"""

    return {
        "title":        title,
        "body_html":    body,
        "vendor":       brand,
        "product_type": f"Apparel & Accessories",
        "status":       "draft",
        "published":    False,
        "tags":         f"embroidery-catalog,{safe_brand},{sname.lower()},custom-embroidery,quote-only,needs-review,{cat_tag},{gender}",
        "options":      [{"name": "Color"}, {"name": "Size"}],
        "variants":     variants,
        "images":       images[:20],
    }

# ── Shopify API ───────────────────────────────────────────────
def get_token():
    try:
        r = requests.post(
            f"https://{SHOPIFY_STORE}/admin/oauth/access_token",
            json={"client_id": SHOPIFY_CLIENT_ID,
                  "client_secret": SHOPIFY_CLIENT_SECRET,
                  "grant_type": "client_credentials"},
            timeout=30)
        if r.status_code == 200:
            t = r.json().get("access_token","")
            print(f"  ✅ Token obtained (starts: {t[:8]}...)")
            return t
        print(f"  ❌ Token failed {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Token error: {e}")
        return None

def sh_h(token):
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

def sh_get(path, token):
    try:
        r = requests.get(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                         headers=sh_h(token), timeout=30)
        return r
    except Exception as e:
        print(f"    ❌ GET error: {e}"); return None

def sh_post(path, data, token, timeout=60):
    try:
        r = requests.post(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                          headers=sh_h(token), json=data, timeout=timeout)
        return r
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        print(f"    ❌ POST error: {e}"); return None

def sh_put(path, data, token):
    try:
        r = requests.put(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                         headers=sh_h(token), json=data, timeout=60)
        return r
    except Exception as e:
        print(f"    ❌ PUT error: {e}"); return None

def get_collections(token):
    r = sh_get("custom_collections.json?limit=250", token)
    if r and r.status_code == 200:
        cols = r.json().get("custom_collections",[])
        return {c["handle"]: c["id"] for c in cols}
    return {}

def find_product(title, token):
    r = sh_get(f"products.json?title={requests.utils.quote(title)}&limit=1", token)
    if r and r.status_code == 200:
        p = r.json().get("products",[])
        if p: return p[0]["id"], p[0].get("status","draft")
    return None, None

def create_product(data, token):
    """Create product with retry on timeout — split variants if needed."""
    r = sh_post("products.json", {"product": data}, token, timeout=90)
    if r and r.status_code == 201:
        return r.json().get("product",{})
    if r is None:
        # Timeout — try with fewer variants
        print(f"    ⚠️  Timeout creating product — retrying with fewer variants...")
        reduced = dict(data)
        reduced["variants"] = data["variants"][:50]
        reduced["images"]   = data["images"][:5]
        r2 = sh_post("products.json", {"product": reduced}, token, timeout=90)
        if r2 and r2.status_code == 201:
            print(f"    ✅ Created with reduced variants ({len(reduced['variants'])})")
            return r2.json().get("product",{})
    if r:
        print(f"    ❌ Create failed {r.status_code}: {r.text[:300]}")
    return None

def update_product(pid, data, token, current_status):
    update = dict(data)
    if current_status == "active":
        update["status"]    = "active"
        update["published"] = True
        tags = [t.strip() for t in update.get("tags","").split(",")
                if t.strip() != "needs-review"]
        update["tags"] = ",".join(tags)
    r = sh_put(f"products/{pid}.json", {"product": update}, token)
    return r and r.status_code == 200

def add_to_collection(pid, cid, token):
    r = sh_post("collects.json",
                {"collect": {"product_id": pid, "collection_id": cid}}, token)
    return r and r.status_code == 201

def set_category(pid, taxonomy_gid, token):
    """Set Shopify product category via GraphQL."""
    try:
        r = requests.post(
            f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json",
            headers=sh_h(token),
            json={"query": """mutation setCategory($input: ProductInput!) {
                productUpdate(input: $input) {
                    product { category { name } }
                    userErrors { message }
                }}""",
                  "variables": {"input": {
                      "id": f"gid://shopify/Product/{pid}",
                      "category": taxonomy_gid
                  }}},
            timeout=20)
        if r and r.status_code == 200:
            data = r.json()
            cat = (data.get("data",{}).get("productUpdate",{})
                   .get("product",{}).get("category",{}))
            if cat:
                print(f"    🏷️  Category: {cat.get('name','')}")
                return True
    except Exception as e:
        print(f"    ⚠️  Category error: {e}")
    return False

def assign_color_images(product, token):
    """Link color images to variants for color-switching."""
    pid      = product["id"]
    variants = product.get("variants", [])
    images   = product.get("images", [])

    color_img  = {}
    for img in images:
        alt = img.get("alt","")
        if " — " in alt:
            color_img[alt.split(" — ",1)[1].strip()] = img["id"]

    color_vars = {}
    for v in variants:
        color_vars.setdefault(v.get("option1","").strip(), []).append(v["id"])

    updated = 0
    for color, img_id in color_img.items():
        vids = color_vars.get(color, [])
        if not vids:
            for k,v in color_vars.items():
                if k.lower() == color.lower():
                    vids = v; break
        if vids:
            r = sh_put(f"products/{pid}/images/{img_id}.json",
                       {"image": {"id": img_id, "variant_ids": vids}}, token)
            if r and r.status_code == 200:
                updated += 1
            time.sleep(0.2)
    if updated:
        print(f"    🎨 {updated} color images linked")

# ── Main ──────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S TO SHOPIFY SYNC")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {len(STYLES)} styles in catalog")
    print("="*60)

    if not SS_USERNAME or not SHOPIFY_CLIENT_ID:
        print("\n❌ Missing credentials"); return

    print("\n🔑 Getting Shopify token...")
    token = get_token()
    if not token: return

    r = sh_get("shop.json", token)
    if not r or r.status_code != 200:
        print("❌ Shopify connection failed"); return
    print(f"✅ Connected: {r.json().get('shop',{}).get('name')}")

    print("\n📦 Fetching collections...")
    collections = get_collections(token)
    print(f"   {len(collections)} collections found")

    stats = {"created":0, "updated":0, "skipped":0, "errors":0}
    current_col = None

    for brand, style_name, col_handle, cat_tag, taxonomy_gid in STYLES:
        # Print section header when collection changes
        if col_handle != current_col:
            current_col = col_handle
            print(f"\n{'═'*55}")
            print(f"📂 {col_handle}")

        print(f"\n  ── {brand} {style_name}")

        # Fetch style
        style = get_style(brand, style_name)
        if not style:
            print(f"     ❌ Not found in S&S — skipping")
            stats["errors"] += 1
            time.sleep(0.5)
            continue

        full_title = f"{style.get('brandName','')} {style.get('styleName','')} — {style.get('title','')}"
        print(f"     Found: {full_title}")

        # Fetch variants and specs
        style_id = style.get("styleID")
        products = get_products(style_id)
        specs    = get_specs(style_id)
        print(f"     {len(products)} SKUs | {len(specs)} specs")

        # Build payload
        payload = build_product(style, products, specs, col_handle, cat_tag)

        # Check if exists in Shopify
        existing_id, existing_status = find_product(payload["title"], token)

        if existing_id:
            label = "⚡ ACTIVE — preserving" if existing_status=="active" else "↩️  Draft — updating"
            print(f"     {label} (ID: {existing_id})")
            if update_product(existing_id, payload, token, existing_status):
                print("     ✅ Updated")
                stats["updated"] += 1
            else:
                print("     ❌ Update failed")
                stats["errors"] += 1
        else:
            created = create_product(payload, token)
            if created:
                pid = created["id"]
                print(f"     ✅ Created as DRAFT (ID: {pid})")
                # Set Shopify category
                set_category(pid, taxonomy_gid, token)
                # Link color images
                assign_color_images(created, token)
                # Add to collection
                cid = collections.get(col_handle)
                if cid:
                    ok = add_to_collection(pid, cid, token)
                    print(f"     📁 {'Added to' if ok else 'Failed adding to'}: {col_handle}")
                else:
                    print(f"     ⚠️  Collection not found: {col_handle}")
                stats["created"] += 1
            else:
                stats["errors"] += 1

        time.sleep(1.0)

    print(f"\n{'='*60}")
    print(f"  COMPLETE")
    print(f"  ✅ Created:  {stats['created']}")
    print(f"  🔄 Updated:  {stats['updated']}")
    print(f"  ⏭️  Skipped:  {stats['skipped']}")
    print(f"  ❌ Errors:   {stats['errors']}")
    print(f"\n  → Shopify Admin → Products → filter: needs-review")
    print("="*60+"\n")

if __name__ == "__main__":
    run()
