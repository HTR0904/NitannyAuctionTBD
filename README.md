# Initial Setup
## Setting up Github
1. Go to Settings > Version Control > Github
2. Click on the '+' sign and log in with your GitHub account

More info can be found here: https://www.jetbrains.com/help/pycharm/set-up-a-github-account.html#github-enterprise

## Setting up for commits
In terminal run:
```
git config --global user.email "abc1234@psu.edu"
git config --global user.name "FirstName LastName"
```

## Cloning this repo
1. On the top menu bar, click on your project name (It should be left of "Version Control") 
2. Click on Clone Repository
3. Enter the HTTPS url of this repo and click Clone
4. (Optional) choose your directory

More info can be found here: https://www.jetbrains.com/help/idea/set-up-a-git-repository.html

## Branching and changes
The repository is setup so that you will always have to commit to a branch first and make a pull request before your changes can be merged onto the main branch.

Pycharm automatically takes care of this for you by creating a ne branch if you attempt to commit on the main branch. However if you prefer more control of how your branches:


1. Create a new branch
```
git checkout -b 'branchName'
```

2. Afterwards, you can start making your changes and codes 
3. Once you're ready to commit, go to the sidebar and click the commit button (Alt+0)
4. Select the files you want to commit + write your commit message
5. Choose either:
   - 'Commit' your changes locally (i.e. changes are only on your device)
     - You can later use 'git push' to push commits to remote branches

   - 'Commit and push' to push your changes to the remote branch (where you can create a pull request)

### Other useful branch codes
Switching branches
```
git checkout "branchName"
```
As a note: the main branch is called `main`
## Pull Requests
The visually easiest way is to go to this repo on github. 

If you recently push a commit to the remote branch, you'll recieve a yellow banner asking if you want to create a pull request
![img.png](img.png)

In the event you don't see this prompt, you can still create a pull request by doing the following on github:
1. In the 'Code' page, select 'Branches'
2. Under 'Your branches' select the branch you want to create a pull request for

### Important note regarding merged PRs
> Branches of merged PRs are deleted automatically.  
> To avoid potential issues or complication, always create a new branch for future commits. <br>
> Avoid attempting to commit to a deleted branch (it won't necessarily break anything, but will take a while to figure out).


## Updating your repository after a pull request
To get the latest version of the code, switch back to the  `main`   branch and run:
```
git pull
```

Afterwards, you can also update your branches to use the latest version of the codebase, by switch to the branch you are working on and run:
```
git rebase main
```
This is primarily to stop potential merge conflicts and resolve them before the pull requests.

## Other useful git commands
Need to switch branch but can't because git is asking you to commit?
Not ready to commit your changes yet?
Use
```
git stash
```
to save your changes locally. After stashing uncommitted changes will be removed from the code.

To get your changes back:
```
git stash pop
```
More on this: https://www.w3schools.com/git/git_stash.asp