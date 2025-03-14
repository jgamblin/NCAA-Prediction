# NCAA Game Predictions

This project aims to predict the outcomes of NCAA basketball games using machine learning models. The code leverages the `scikit-learn` library for building and evaluating the models, and the `cbbpy` library for scraping game data.

## High Confidence Predictions:
| Game Day       | Home Team              | Away Team                  | Predicted Winner       |   Win Probability |
|:---------------|:-----------------------|:---------------------------|:-----------------------|------------------:|
| March 14, 2025 | Grand Canyon Lopes     | California Baptist Lancers | Grand Canyon Lopes     |              0.95 |
| March 14, 2025 | Memphis Tigers         | Wichita State Shockers     | Memphis Tigers         |              0.92 |
| March 14, 2025 | Norfolk State Spartans | Morgan State Bears         | Norfolk State Spartans |              0.91 |
| March 14, 2025 | UC San Diego Tritons   | UC Santa Barbara Gauchos   | UC San Diego Tritons   |              0.9  |
| March 14, 2025 | Akron Zips             | Toledo Rockets             | Akron Zips             |              0.89 |
| March 14, 2025 | North Texas Mean Green | Tulsa Golden Hurricane     | North Texas Mean Green |              0.88 |
| March 14, 2025 | Auburn Tigers          | Ole Miss Rebels            | Auburn Tigers          |              0.87 |
| March 14, 2025 | Utah Valley Wolverines | Seattle U Redhawks         | Utah Valley Wolverines |              0.86 |
| March 14, 2025 | Quinnipiac Bobcats     | Iona Gaels                 | Quinnipiac Bobcats     |              0.83 |
| March 14, 2025 | UC Irvine Anteaters    | Cal Poly Mustangs          | UC Irvine Anteaters    |              0.81 |

Model Accuracy For 2025: 0.7765

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

**Last updated:** March 14, 2025 at 12:38 PM
