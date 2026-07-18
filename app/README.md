apps/
└── sample_NB/
    ├── README.md          ← this file
    └── app/
    	├── images/        ← ✏️  add an image/icon for app. 
        ├── app.py         ← ✏️  ENTRY POINT  (5 lines to edit per new app)
        ├── app.env        ← ✏️  ENV CONFIG   (set LOGS_PATH and extras here)
        ├── sample_NB.py   ← ✏️  YOUR PAYLOAD (Inlcude UI, etc. must run using **streamlit run sample_NB**  to make sure it work. )
        │
        ├── sandbox.py     ← 🔒  framework — do not edit
        ├── startup.py     ← 🔒  framework — do not edit
        └── logs.py        ← 🔒  framework — do not edit
        
        
        
To test, 
streamlit run apps/sample_NB/app/app.py
