# NCAA Game Predictions

This project aims to predict the outcomes of NCAA basketball games using machine learning models. The code leverages the `scikit-learn` library for building and evaluating the models, and the `cbbpy` library for scraping game data.

## High Confidence Predictions:
| Game Day       | Home Team            | Away Team                    | Predicted Winner     |   Win Probability |
|:---------------|:---------------------|:-----------------------------|:---------------------|------------------:|
| March 15, 2025 | Yale Bulldogs        | Princeton Tigers             | Yale Bulldogs        |              0.89 |
| March 15, 2025 | Memphis Tigers       | Tulane Green Wave            | Memphis Tigers       |              0.86 |
| March 15, 2025 | Liberty Flames       | Jacksonville State Gamecocks | Liberty Flames       |              0.85 |
| March 15, 2025 | Bryant Bulldogs      | Maine Black Bears            | Bryant Bulldogs      |              0.85 |
| March 15, 2025 | St. John's Red Storm | Creighton Bluejays           | St. John's Red Storm |              0.82 |
| March 15, 2025 | Houston Cougars      | Arizona Wildcats             | Houston Cougars      |              0.8  |
| March 15, 2025 | Cornell Big Red      | Dartmouth Big Green          | Cornell Big Red      |              0.8  |

Model Accuracy For 2025: 0.7507

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

**Last updated:** March 15, 2025 at 12:40 PM
