IMAGE_GALLERY_STYLESHEET = """
    #imageGalleryWidget, #imageGalleryScrollArea, #galleryScrollContent {
        background-color: #8db9f7;
        border: none;
    }

    #imageGalleryWidget {
        border-radius: 1px;
    }
    
    QLabel#imageCategoryHeader {
        font-weight: bold;
        font-size: 11pt;
        color: #4b3370;
        background-color: transparent;
        margin-top: 10px;
    }

    /* A bélyegkép konténere (QWidget) - Keret nélkül, csak a belső tér (padding) a fontos */
    #imageThumbnailWidget {
        background-color: transparent;
        padding: 2px; /* Ez a tér a keret és a gombok között */
    }

    /* A képet tartalmazó QLabel - IDE KERÜL A KERET (egyszínű, lapos stílussal) */
    QLabel#thumbnailImageLabel {
        background-color: transparent;
        border: 1px solid #bacfe8; /* Egy kellemes, sötétebb kék árnyalat */
        border-radius: 2px;
    }

    QLabel#thumbnailFilenameLabel {
        font-size: 8pt;
        color: #DDDDDD;
    }
    
    #imageThumbnailWidget QPushButton {
        background-color: rgba(255, 255, 255, 150);
        border: 1px solid rgba(0, 0, 0, 50);
        border-radius: 4px;
    }
    #imageThumbnailWidget QPushButton:hover {
        background-color: rgba(255, 255, 255, 220);
    }

    #toggleExpandButton {
        background-color: #a6d5ff;
        border: 1px solid #ccdff0;
        border-radius: 2px;
    }

    #toggleExpandButton:hover {
        background-color: #7e7e8a;
    }

    #toggleExpandButton:pressed {
        background-color: #4e4e5a;
    }
"""