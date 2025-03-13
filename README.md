# NCAA Game Predictions

This project aims to predict the outcomes of NCAA basketball games using machine learning models. The code leverages the `scikit-learn` library for building and evaluating the models, and the `cbbpy` library for scraping game data.

## High Confidence Predictions:
| Game Day       | Home Team                         | Away Team                   | Predicted Winner                  |   Win Probability |
|:---------------|:----------------------------------|:----------------------------|:----------------------------------|------------------:|
| March 13, 2025 | Duke Blue Devils                  | Georgia Tech Yellow Jackets | Duke Blue Devils                  |              0.97 |
| March 13, 2025 | St. John's Red Storm              | Butler Bulldogs             | St. John's Red Storm              |              0.95 |
| March 13, 2025 | Utah State Aggies                 | UNLV Rebels                 | Utah State Aggies                 |              0.94 |
| March 13, 2025 | Houston Cougars                   | Colorado Buffaloes          | Houston Cougars                   |              0.94 |
| March 13, 2025 | New Mexico Lobos                  | San José State Spartans     | New Mexico Lobos                  |              0.94 |
| March 13, 2025 | Creighton Bluejays                | DePaul Blue Demons          | Creighton Bluejays                |              0.92 |
| March 13, 2025 | Akron Zips                        | Bowling Green Falcons       | Akron Zips                        |              0.92 |
| March 13, 2025 | Wisconsin Badgers                 | Northwestern Wildcats       | Wisconsin Badgers                 |              0.92 |
| March 13, 2025 | Louisville Cardinals              | Stanford Cardinal           | Louisville Cardinals              |              0.92 |
| March 13, 2025 | George Washington Revolutionaries | Fordham Rams                | George Washington Revolutionaries |              0.91 |

Model Accuracy For 2025: 0.7536

## Description

The main functionalities of this project include:

- Scraping NCAA basketball game data using the `cbbpy` library.
- Preprocessing the data for model training.
- Building and evaluating machine learning models using `scikit-learn`.
- Generating predictions for upcoming games.
- Exporting predictions to [NCAA_Game_Predictions.csv](NCAA_Game_Predictions.csv).
- Updating the README file with the latest model performance and high confidence predictions.

## Libraries Used

- [scikit-learn](https://scikit-learn.org/stable/): A machine learning library for Python that provides simple and efficient tools for data mining and data analysis.
- [cbbpy](https://pypi.org/project/cbbpy/): A Python library for scraping NCAA basketball data.

**Last updated:** March 13, 2025 at 12:33 PM
