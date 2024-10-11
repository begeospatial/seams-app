# Installation

`SEAMS-APP` can be installed and run in two ways: 

## Using github repository
- clone the github repository or download the zip file of the repo.
- (optional) Change the name of the `seams-app-main` subdirectory (from the zip file) for `seam-app`
- within the subfolder `seams_app` [not to be confused with the parent folder `seams-app-<main>`] create a new subfolder called `data`
  
### using a dedicated python environment
- Create a new python environment using the `requirements.txt` file
- activate your environment and run `streamlit run  <localpath>/seams-app/seams_app/app.py`

### complement with docker (does not require a dedicated python environment)
- change the local volume path in the provided `docker-compose.yml` file to match the installation of your local github repository, i.e. `<localpath>/seams-app/seams_app` note in windows you need to use something like `- //c/Users/<username>/<localpath>/seams-app/:/home/seams-app-user/seams-app`
- using a terminal window (powershell):
  ```
  cd //c/Users/<username>/<localpath>/seams-app/
  docker-compose up -d
  ```

# First Use:
- On a browser window type: `http://localhost:8501/`
- ensure you have created the subfolder `data` within the subfolder `seams_app` [not to be confused with the parent folder `seams-app-<main>`].
- Create a new survey `survey_name`
- Copy the video files into the `.../seams_app/data/SURVEYS/<survey_name>/VIDEOS/`
- Manually fill in or Copy & Paste in to the SEAMS-APP the stations data and videos data.

  
