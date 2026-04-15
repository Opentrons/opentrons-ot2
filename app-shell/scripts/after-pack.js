// after the app is packaged and before it is signef, on osx build in python
'use strict'

const eblib = require('builder-util')
const installPython = require('./python-install')
const path = require('path')
const fs = require('fs-extra')
const { execFileSync } = require('child_process')

// copy Assets.car
async function copyAssetCar(appOutDir, productFilename) {
  const source = path.join(__dirname, '..', 'build', 'Assets.car')
  if (!(await fs.pathExists(source))) return

  const target = path.join(
    appOutDir,
    `${productFilename}.app`,
    'Contents',
    'Resources',
    'Assets.car'
  )
  await fs.ensureDir(path.dirname(target))
  await fs.copy(source, target)
}

async function logPackagedAppSizes(appBase) {
  const inspectPaths = [
    appBase,
    path.join(appBase, 'Contents', 'Resources', 'app.asar'),
    path.join(appBase, 'Contents', 'Resources', 'Assets.car'),
    path.join(appBase, 'Contents', 'Frameworks'),
  ]

  for (const inspectPath of inspectPaths) {
    if (!(await fs.pathExists(inspectPath))) continue

    try {
      const size = execFileSync('du', ['-sh', inspectPath], {
        encoding: 'utf8',
      }).trim()
      console.log(`after-pack: size ${size}`)
    } catch (error) {
      console.warn(`after-pack: failed to inspect size for ${inspectPath}`, error)
    }
  }
}

module.exports = async function afterPack(context) {
  const { platform, arch, electronPlatformName, outDir, appOutDir, packager } =
    context
  const archStr = eblib.Arch[arch]
  console.log('after-pack: context', context)
  console.log(
    `after-pack: outDir: ${outDir}, applicationOutDir: ${appOutDir}, archStr ${archStr}`
  )
  const platformName = electronPlatformName ?? platform.nodeName
  // arch 4 is universal. sorry. it's not in the arch enum of the builder-util we have for some reason.
  if (platformName === 'darwin') {
    const productFilename = packager.appInfo.productFilename
    const appBase = path.join(appOutDir, `${productFilename}.app`)

    await copyAssetCar(appOutDir, productFilename)
    await logPackagedAppSizes(appBase)

    if (arch !== 4) {
      console.log(
        `After-pack: on darwin we only pack python on final universal app creation, not intermediate ${archStr} app creation`
      )
      return true
    } else {
      console.log(
        `After-pack: Packing python for darwin/universal as darwin/x64 to ${appBase}`
      )
      const result = await installPython(platformName, ['x64'], appBase)
      await logPackagedAppSizes(appBase)
      return result
    }
  } else {
    console.log(
      `After-pack: Packing python for ${platformName}/${archStr} to ${appOutDir}`
    )
    return installPython(platformName, [archStr], appOutDir)
  }
}
