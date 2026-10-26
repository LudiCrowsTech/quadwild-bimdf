# LCT Engine CI - setup guide

This setup keeps our fork of QuadWild up to date and publishes ready-made
engine downloads for the Ariadne add-on, automatically.

What it does every night (03:17 UTC):
1. Pulls new commits from upstream (`cgg-bern/quadwild-bimdf`) into the fork.
2. If there is something new, builds `quadwild` and `quad_from_patches` for
   Windows, Linux and macOS.
3. Tests each build on 4 generated meshes (must give >= 95% quads).
4. Publishes a GitHub release with 3 zip files and updates `manifest.json`,
   which the add-on reads to find the newest engine.

## One-time setup

1. Go to https://github.com/cgg-bern/quadwild-bimdf and click **Fork**.
   Choose owner **LudiCrowsTech** and keep the name `quadwild-bimdf`.
2. Add the files from this folder to the fork's default branch (`main`),
   keeping the same layout:
   `.github/workflows/lct-engine.yml` and the `lct/` folder.
   (GitHub web: *Add file > Upload files*, drag the folders in, commit.)
3. In the fork open **Settings > Actions > General**:
   - Under "Actions permissions" choose **Allow all actions and reusable workflows**.
   - Under "Workflow permissions" choose **Read and write permissions**, then Save.
4. Open the **Actions** tab. If GitHub shows a green button to enable workflows
   on the fork, click it (forks have scheduled workflows off by default).
5. Optional, manual approval of every release: **Settings > Environments >
   New environment**, name it exactly `release`, tick **Required reviewers**
   and add yourself. Without this, releases are published automatically.
6. First run: **Actions > LCT Engine > Run workflow**, set **force = true**,
   click the green button. It takes roughly 20-40 minutes. If you set up the
   reviewer in step 5, open the run and click **Review deployments > Approve**
   when the build finishes.

## Result

- Releases (tags `lct-<date>-<commit>`): the **Releases** page of the fork.
- The add-on reads this URL:
  https://raw.githubusercontent.com/LudiCrowsTech/quadwild-bimdf/manifest/manifest.json

## Good to know

- If a run fails (build error, merge conflict, failed test), GitHub sends an
  email to the repo owner. Open the failed run in the Actions tab to read why.
- Merge conflict: upstream changed something we also changed. The job stops
  and nothing is published; the fork must be merged by hand once.
- If upstream edits files in `.github/workflows/`, GitHub refuses the
  automatic push. Merge upstream manually once (e.g. GitHub's **Sync fork**
  button, then re-run).
- GitHub pauses scheduled workflows after 60 days without repo activity. Run
  the workflow manually once to wake it up.
- Local test of the engine: `python3 lct/regress.py --bin <folder with the two
  binaries> --config config --out metrics.json` (add `--baseline old.json` to
  compare against an earlier run).
