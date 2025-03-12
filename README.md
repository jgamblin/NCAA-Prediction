# NCAA Game Predictions

This project aims to predict the outcomes of NCAA basketball games using machine learning models. The code leverages the `scikit-learn` library for building and evaluating the models, and the `cbbpy` library for scraping game data.

## High Confidence Predictions:
| Game Day       | Home Team                     | Away Team                      | Predicted Winner              |   Win Probability |
|:---------------|:------------------------------|:-------------------------------|:------------------------------|------------------:|
| March 12, 2025 | Utah Valley Wolverines        | Utah Tech Trailblazers         | Utah Valley Wolverines        |              0.99 |
| March 12, 2025 | Norfolk State Spartans        | Maryland Eastern Shore Hawks   | Norfolk State Spartans        |              0.98 |
| March 12, 2025 | South Carolina State Bulldogs | Coppin State Eagles            | South Carolina State Bulldogs |              0.98 |
| March 12, 2025 | Jacksonville State Gamecocks  | Florida International Panthers | Jacksonville State Gamecocks  |              0.97 |
| March 12, 2025 | Villanova Wildcats            | Seton Hall Pirates             | Villanova Wildcats            |              0.96 |
| March 12, 2025 | Grand Canyon Lopes            | UT Arlington Mavericks         | Grand Canyon Lopes            |              0.94 |
| March 12, 2025 | UNLV Rebels                   | Air Force Falcons              | UNLV Rebels                   |              0.94 |
| March 12, 2025 | SMU Mustangs                  | Syracuse Orange                | SMU Mustangs                  |              0.93 |
| March 12, 2025 | Baylor Bears                  | Kansas State Wildcats          | Baylor Bears                  |              0.87 |
| March 12, 2025 | Liberty Flames                | UTEP Miners                    | Liberty Flames                |              0.86 |

Model Accuracy For 2025: 0.7717

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

**Last updated:** March 12, 2025 at 09:46 PM
