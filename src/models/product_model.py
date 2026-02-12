from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import enum
import re

@dataclass
class FacebookData:
    """
    Egy termékhez kapcsolódó összes Facebook-specifikus adatot és állapotot tároló struktúra.
    """
    # --- 1. TARTALOM (Content) ---
    # A felhasználó által szerkeszthető szöveges tartalmak.
    
    post_text: Optional[str] = field(default=None, metadata={"description": "A normál Facebook oldali poszthoz szánt szöveg."})
    ad_text: Optional[str] = field(default=None, metadata={"description": "Egy fizetett Facebook hirdetéshez szánt, esetleg eltérő szöveg."})
    hashtags: Optional[str] = field(default=None, metadata={"description": "A poszthoz/hirdetéshez tartozó hashtagek, vesszővel elválasztva (pl. #antik, #butor)."})
    selected_images: List[str] = field(default_factory=list, metadata={"description": "A Facebook poszthoz kiválasztott képfájlok neveinek listája."})

    # --- 2. ÁLLAPOT és NYOMONKÖVETÉS (State & Tracking) ---
    # Az automatizáció által beállított, csak olvasható állapotjelzők.

    is_posted: bool = field(default=False, metadata={"description": "Igaz, ha a termékről már készült poszt a Facebook oldalon."})
    is_ad_created: bool = field(default=False, metadata={"description": "Igaz, ha a termékből már készült fizetett hirdetés."})
    
    posted_at: Optional[datetime] = field(default=None, metadata={"description": "A legutóbbi sikeres posztolás időbélyege."})
    
    post_id: Optional[str] = field(default=None, metadata={"description": "A Facebook által generált egyedi poszt azonosító. Kulcsfontosságú a későbbi szerkesztéshez/törléshez."})
    post_url: Optional[str] = field(default=None, metadata={"description": "A létrehozott Facebook poszt közvetlen URL-je."})
    
    ad_id: Optional[str] = field(default=None, metadata={"description": "A Facebook által generált egyedi hirdetés azonosító."})

    # --- 3. PIACTÉR-SPECIFIKUS ADATOK (Marketplace Data) ---
    # Olyan adatok, amik eltérhetnek a termék alapadataitól.

    marketplace_price: Optional[float] = field(default=None, metadata={"description": "Opcionális, a Facebook Marketplace-en megjelenítendő ár. Ha None, a termék alapárát használjuk."})

    # --- 4. MENEDZSMENT és HIBAKEZELÉS (Management & Error Handling) ---
    # A rendszer belső működéséhez szükséges mezők.

    last_synced_at: Optional[datetime] = field(default=None, metadata={"description": "Az utolsó időpont, amikor az alkalmazás API-n keresztül szinkronizálta a poszt állapotát (pl. analitikát kért le)."})
    error_message: Optional[str] = field(default=None, metadata={"description": "Ha az automatizált posztolás/hirdetésfeladás hibára fut, ide kerül a hibaüzenet."})

    def to_dict(self) -> Dict[str, Any]:
        """
        Szerializálja az objektumot egy szótárba, kezelve a datetime mezőket.
        """
        data = self.__dict__.copy() # Másolatot készítünk, hogy ne módosítsuk az eredeti objektumot
        
        # Datetime objektumok konvertálása ISO formátumú stringgé
        if isinstance(data.get('posted_at'), datetime):
            data['posted_at'] = data['posted_at'].isoformat()
        
        if isinstance(data.get('last_synced_at'), datetime):
            data['last_synced_at'] = data['last_synced_at'].isoformat()
            
        return data

class MainCategory(enum.Enum):
    ANTIQUE_FURNITURE = "Antik Bútor"  
    HOME_ACCESSORY = "Lakáskiegészítő"     
    UNCATEGORIZED = "Nincs fő kategória" 

    def to_slug(self) -> str:
        return _sanitize_for_slug(self.value)

    @property
    def display_name(self) -> str:
        return self.value 


def _sanitize_for_slug(s: Optional[str]) -> str:
    """
    Tisztítja és slug-osítja a bemeneti stringet, kezelve a magyar ékezetes karaktereket.
    """
    if not s:
        return ""
    
    s = s.lower().strip()
    
    # Magyar ékezetes karakterek cseréje ASCII megfelelőkre
    s = s.replace('á', 'a')
    s = s.replace('é', 'e')
    s = s.replace('í', 'i')
    s = s.replace('ó', 'o')
    s = s.replace('ö', 'o')
    s = s.replace('ő', 'o')
    s = s.replace('ú', 'u')
    s = s.replace('ü', 'u')
    s = s.replace('ű', 'u')
    
    # Space-ek cseréje kötőjelekre
    s = s.replace(' ', '-') 
    
    # Nem alfanumerikus karakterek és nem kötőjelek eltávolítása
    s = re.sub(r'[^\w-]', '', s) 
    
    # Többszörös kötőjelek cseréje egyetlenre, és a kezdő/záró kötőjelek eltávolítása
    s = re.sub(r'[-]+', '-', s).strip('-') 
    
    return s

@dataclass
class Product:
    id: str = field(metadata={"description": "Egyedi azonosító a termékhez (pl. Galéria Savaria termékkód). Ez a belső primary key."})
    main_category: MainCategory = field(metadata={"description": "Termék fő kategóriája enumként."}) 
    main_category_slug: str = field(metadata={"description": "A fő kategória slug-osított string formában (pl. 'antikbutor') a könyvtárszerkezethez."}) 
    title: str = field(metadata={"description": "Termék neve vagy címe."})
    price_numeric: float = field(metadata={"description": "Tisztított, numerikus ár érték (pl. 12345.0)."})
    price_raw: str = field(metadata={"description": "Nyers ársztring a weboldalról (pl. '12 345 Ft')."})

    created_at: datetime = field(default_factory=datetime.now, metadata={"description": "A termék rekordjának belső létrehozási dátuma az alkalmazásban."})
    
    sub_category_slug: Optional[str] = field(default_factory=lambda: _sanitize_for_slug("Nincs alkategória"), metadata={"description": "Az alkategória slug-osított string formában (pl. 'asztal') a könyvtárszerkezethez."}) 
    product_type: Optional[str] = field(default_factory=lambda: "Nincs terméktípus", metadata={"description": "A termék specifikus típusa (pl. 'Kabinetszekrény', 'Tükör', 'Kanapé')."})
    product_type_slug: Optional[str] = field(default_factory=lambda: _sanitize_for_slug("Nincs terméktípus"), metadata={"description": "A termék specifikus típusának slug-osított string formája (pl. 'etkezoasztal') a könyvtárszerkezethez."})

    style_era: List[str] = field(default_factory=list, metadata={"description": "A termék stílusa és/vagy korszaka (pl. 'Neoreneszánsz', 'Lajos stílusú')."})
    color: Optional[str] = field(default=None, metadata={"description": "A termék fő színe (pl. 'barna', 'fekete')."})

    description: Optional[str] = field(default=None, metadata={"description": "A termék fő leírása."})

    currency: str = field(default="HUF", metadata={"description": "Pénznem kód (pl. 'HUF', 'EUR')."})

    num_original_images: int = 0
    num_transparent_images: int = 0
    num_mixed_images: int = 0
    
    gs_watchers: int = 0
    gs_views: int = 0
    jf_position: Optional[int] = field(default=None, metadata={"description": "A termék abszolút pozíciója a Jófogás hirdetési listájában (1-től indexelve)."})

    is_gs_dependent: bool = field(default=True, metadata={"description": "Jelzi, hogy a termék Galéria Savaria függőségű-e (pl. onnan származik)."})
    is_sold: bool = field(default=False, metadata={"description": "Jelzi, hogy a termék eladva van-e. Az eladott termékek nem törlődnek azonnal."})
    needs_manual_category_review: bool = field(default=False, metadata={"description": "Jelzi, ha a termék manuális kategória felülvizsgálatot igényel."})
    needs_upload: bool = field(default=True, metadata={"description": "Jelzi, hogy a termék adatainak és/vagy képeinek feltöltése szükséges a távoli szerverre."}) # ÚJ MEZŐ
    is_delisted_on_gs: bool = field(default=False, metadata={"description": "Jelzi, ha egy GS függő termék már nem található a weboldalon."})

    image_url: Optional[str] = field(default=None, metadata={"description": "A termék elsődleges képének URL-je a weboldalon."})
    product_url: Optional[str] = field(default=None, metadata={"description": "A termék oldalpája a weboldalon."})

    additional_attributes: Dict[str, Any] = field(default_factory=dict, metadata={"description": "Szótár bármilyen forrás-specifikus vagy extra attribútumhoz, ami nem szerepel a fő mezők között (pl. méretek, anyag, linkek, feltöltési dátumok, böngésző állapot adatok)."})
    facebook_data: FacebookData = field(default_factory=FacebookData)

    @property
    def is_in_sync_and_ready(self) -> bool:
        """
        Igaz értéket ad vissza, ha a termék teljesen szinkronizált,
        kategorizált, van képe és nincsenek rajta figyelmeztetések.
        Ez az állapot felel meg a lista nézet alapértelmezett színének.
        """
        return not (
            self.is_sold or
            self.is_delisted_on_gs or
            self.main_category == MainCategory.UNCATEGORIZED or
            self.num_mixed_images == 0 or
            self.needs_manual_category_review or
            self.needs_upload
        )

    @property
    def is_valid_for_upload(self) -> bool:
        """
        Igaz értéket ad vissza, ha a termék állapota logikailag engedélyezi a feltöltést
        (vagyis nincs olyan kritikus hibája, ami ezt megakadályozná).
        Figyelem: Ez a flag önmagában nem ellenőrzi a 'needs_upload' állapotot!
        """
        return (
            not self.is_sold and
            not self.is_delisted_on_gs and
            self.main_category != MainCategory.UNCATEGORIZED and
            self.num_mixed_images > 0 and
            not self.needs_manual_category_review
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "main_category": self.main_category.value, # Magyar név mentése
            "main_category_slug": self.main_category_slug,
            "title": self.title,
            "price_numeric": self.price_numeric,
            "price_raw": self.price_raw,

            "created_at": self.created_at.isoformat(),
            "sub_category_slug": self.sub_category_slug,
            "product_type": self.product_type,
            "product_type_slug": self.product_type_slug,
            "style_era": self.style_era,
            "color": self.color,
            "description": self.description,
            "currency": self.currency,
            "num_original_images": self.num_original_images,
            "num_transparent_images": self.num_transparent_images,
            "num_mixed_images": self.num_mixed_images,
            "gs_watchers": self.gs_watchers,
            "gs_views": self.gs_views,
            "jf_position": self.jf_position,
            "is_gs_dependent": self.is_gs_dependent,
            "is_sold": self.is_sold,
            "needs_manual_category_review": self.needs_manual_category_review,
            "needs_upload": self.needs_upload,
            "is_delisted_on_gs": self.is_delisted_on_gs,
            "image_url": self.image_url,
            "product_url": self.product_url,
            "additional_attributes": self.additional_attributes,
            "facebook_data": self.facebook_data.to_dict() if self.facebook_data else None,
        }
        return {k: v for k, v in data.items() if v is not None}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Product":
        processed_data = data.copy()

        product_id = processed_data.pop('id', None)
        if product_id is None:
            raise ValueError("Hiányzó kötelező mező: 'id'.")

        product_title = processed_data.pop('title', None)
        if product_title is None:
            raise ValueError("Hiányzó kötelező mező: 'title'.")

        product_price_numeric = processed_data.pop('price_numeric', None)
        if product_price_numeric is None:
            raise ValueError("Hiányzó kötelező mező: 'price_numeric'.")
        
        main_cat_value_from_json = processed_data.pop('main_category', None)
        if main_cat_value_from_json is None:
            raise ValueError("Hiányzó kötelező mező: 'main_category'.")
        try:
            main_category_enum = MainCategory(main_cat_value_from_json) # Value-ból konvertálunk
        except ValueError:
            print(f"Figyelem: A 'main_category' mező értéke '{main_cat_value_from_json}' nem érvényes MainCategory VALUE. Alapértelmezettre állítva.")
            main_category_enum = MainCategory.UNCATEGORIZED
        except Exception as e:
            print(f"Hiba a 'main_category' enum konvertálásakor ('{main_cat_value_from_json}'): {e}")
            main_category_enum = MainCategory.UNCATEGORIZED


        main_category_slug = processed_data.pop('main_category_slug', None)
        if main_category_slug is None:
            main_category_slug = main_category_enum.to_slug()

        product_price_raw = processed_data.pop('price_raw', None)
        if product_price_raw is None:
            if 'price' in processed_data:
                product_price_raw = processed_data.pop('price')
            else:
                raise ValueError("Hiányzó kötelező mező: 'price_raw' vagy 'price'.")

        created_at_val = processed_data.pop('created_at', None)
        created_at_dt = datetime.fromisoformat(created_at_val) if isinstance(created_at_val, str) else datetime.now()
        
        fb_data_dict = processed_data.pop('facebook_data', None)
        
        # Dátum stringek konvertálása datetime objektumokká
        if fb_data_dict:
            if 'posted_at' in fb_data_dict and isinstance(fb_data_dict['posted_at'], str):
                fb_data_dict['posted_at'] = datetime.fromisoformat(fb_data_dict['posted_at'])
            if 'last_synced_at' in fb_data_dict and isinstance(fb_data_dict['last_synced_at'], str):
                fb_data_dict['last_synced_at'] = datetime.fromisoformat(fb_data_dict['last_synced_at'])
        
        # Létrehozzuk a FacebookData objektumot a szótárból, vagy egy üreset, ha nem létezik.
        facebook_data_obj = FacebookData(**fb_data_dict) if fb_data_dict else FacebookData()

        init_args = {
            'id': product_id,
            'main_category': main_category_enum,
            'main_category_slug': main_category_slug,
            'title': product_title,
            'price_numeric': product_price_numeric,
            'price_raw': product_price_raw,

            'created_at': created_at_dt,
            'sub_category_slug': processed_data.pop('sub_category_slug', None) or _sanitize_for_slug("Nincs alkategória"), 
            'product_type': processed_data.pop('product_type', None) or "Nincs terméktípus", 
            'product_type_slug': processed_data.pop('product_type_slug', None) or _sanitize_for_slug("Nincs terméktípus"), 
            'style_era': processed_data.pop('style_era', []),
            'color': processed_data.pop('color', None),
            'description': processed_data.pop('description', None),
            'currency': processed_data.pop('currency', "HUF"),
            
            # KÉP DARABSZÁMLÁLÓK BETÖLTÉSE A JSON-BÓL
            'num_original_images': data.get('num_original_images', 0), 
            'num_transparent_images': data.get('num_transparent_images', 0), 
            'num_mixed_images': data.get('num_mixed_images', 0), 

            'gs_watchers': processed_data.pop('gs_watchers', 0),
            'gs_views': processed_data.pop('gs_views', 0),
            'jf_position': processed_data.pop('jf_position', None),
            'is_gs_dependent': processed_data.pop('is_gs_dependent', True),
            'is_sold': processed_data.pop('is_sold', False),
            'needs_manual_category_review': processed_data.pop('needs_manual_category_review', False),
            'needs_upload': processed_data.pop('needs_upload', True),
            'is_delisted_on_gs': processed_data.pop('is_delisted_on_gs', False),
            'image_url': processed_data.pop('image_url', None),
            'product_url': processed_data.pop('product_url', None),
            'additional_attributes': processed_data.pop('additional_attributes', {}),
            'facebook_data': facebook_data_obj, 
        }
        
        if processed_data:
            init_args['additional_attributes'].update(processed_data)

        return Product(**init_args)