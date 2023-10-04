# Bubble Shooter

![Screenshot](https://github.com/A-Paint-Brush/Bubble-Shooter/assets/96622265/e095ef27-75b9-4b2c-93ae-b4302f69dc18)

(Above is a screenshot of the level editor)

This project is a simple bubble shooter game written in Python, with SDL as the graphics library. And yes, this is heavily inspired by _Bubble Witch Saga_.

## WIP Notice

This project is **unfinished**, and development won't be resumed for some time as I'm busy applying for university. I would say the project is currently in an about 35% finished state (everything takes so long to make when you aren't using a game engine...). Below are more details about both finished and unfinished goals.

### Level Editor

The editor is currently perfectly functional (as seen by the screenshot above), but there are still a few details and missing features. For example, the level editor currently simply centers itself in the middle of the window when it is resized. I would like to change it to fully make use of the new window size (mainly by enlarging the bubbles that make up the level, other UI elements will simply move). Below is a (not full!) list of important things that I plan to add:

- Better resizing behavior, as mentioned above.
- A "preview" bubble that always appears under the mouse cursor. Without this, it is not clear where the bubble will be placed on click.
- Functionality to **export to**/**load from** a file. As for the file format, I'm still debating whether to use Python's `pickle` module, use a textual serialization format like XML, or write my own file format.

### Gameplay

Sadly, so far I've been working only on the level editor, so currently there's no way to actually play the levels. Here's a list of main things I hope to achieve:

- A bubble-clearing animation. When a "shot" bubble hits the bubbles in the level, a brightening animation should spread over connected bubbles starting from the shot one. When each bubble reaches full brightness, they will pop off the level (see below).
- Some simple physics will be needed to animate bubbles that have been "popped off" the level. I'm thinking they should gain a random amount of "upward" velocity, and a random amount of horizontal velocity. After that, they will simply receive a fixed amount of downward acceleration (gravity). No collision physics will be needed (thankfully) since they will simply fall out of the screen.
- A short dotted line to give a preview of the path the bubble will take from the launcher.
- A smooth scrolling animation whenever the level has to move down.
- Some kind of (runtime generated) simple pattern along the top of the level so the bubbles will not appear to be hanging from nothing.
- Some sort of high score table that is associated with each unique level file. I'm thinking I will keep a local database where score information is associated with the MD5 hash of a level file (not including the filename), that way score information won't have to be stored inside the level file (which would be a terrible idea), and the level file can also be moved around and renamed without losing associated high-scores.

## Installation

As the project is still work in progress, I haven't bothered to create any builds or MSI installers yet. I will probably only do so when the project is completed, and not any earlier. For now, you'll just have to run the source code. This project uses Python 3.8 features (such as the walrus operator) in a few places, so make sure to use at least that version of Python. Note that you can run `pip3 install -r requirements.txt` to quickly install all packages required to run this project.

## Credits

The fonts in `./Fonts` are all distributed by Microsoft, while all images in `./Images` and `./Unused` are drawn by me so far.
