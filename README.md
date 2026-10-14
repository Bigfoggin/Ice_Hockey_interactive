# Ice_Hockey_interactive


The purpose of this repo is to develop an interactive data-oriented project that makes ice hockey more engaging.



## Repo Working Tree

The code will expect the following structure.


(note: if you want to check the working tree on linux just type this into the terminal: "find . -type d -not -path '*/.*' | sed -e 's/[^-][^\/]*\// |-- /g' -e 's/|\([^ ]\)/|-- \1/'")

```
.   (Ice_hockey_interactive)
├── notebooks
├── doc
├── data
│   ├── match_data
│   ├── us_data
│   └── player_data
├── src
└── competition_files
```

## convert_excel_to_csv.py

once you put the data in the right place, run convert_excel_to_csv.py to... obviously convert the excel files to csv.