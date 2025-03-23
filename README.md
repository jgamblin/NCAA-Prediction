# NCAA Game Predictions

This project aims to predict the outcomes of NCAA basketball games using machine learning models. The code leverages the `scikit-learn` library for building and evaluating the models, and the `cbbpy` library for scraping game data.

## High Confidence Predictions:
| Game Day       | Home Team           | Away Team                    | Predicted Winner    |   Win Probability |
|:---------------|:--------------------|:-----------------------------|:--------------------|------------------:|
| March 23, 2025 | SMU Mustangs        | Oklahoma State Cowboys       | SMU Mustangs        |              0.94 |
| March 23, 2025 | UC Irvine Anteaters | Jacksonville State Gamecocks | UC Irvine Anteaters |              0.87 |
| March 23, 2025 | San Francisco Dons  | Loyola Chicago Ramblers      | San Francisco Dons  |              0.85 |
| March 23, 2025 | Florida Gators      | UConn Huskies                | Florida Gators      |              0.84 |## Description

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

**Last updated:** March 23, 2025 at 12:46 PM
