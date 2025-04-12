# dbgdtct

## Desctiption
dbgdtct is a python tool that will help you detect if the web application is deployed in debug mode 

## Installation
```
git clone https://github.com/yousseflahouifi/dbdtct.git
```

## setup
Create a virtual environnement

```
python3 -m venv myenv
source myenv/bin/activate
```

install packages

```
pip3 install aiohttp requests
```

## Usage

To scan a single target application
```
python dbgdtct.py -u https://target.com 
```
To scan multiple targets and URLs
```
python dbgdtct.py -l list.txt
```

## example

```
python dbdtct.py -u https://target.com

  ,--.,--.      ,--.  ,--.          ,--.   
 ,-|  ||  |-.  ,-|  |,-'  '-. ,---.,-'  '-. 
' .-. || .-. '' .-. |'-.  .-'| .--''-.  .-' 
\ `-' || `-' |\ `-' |  |  |  \ `--.  |  |   
 `---'  `---'  `---'   `--'   `---'  `--'   
            dbdtct — Web Debug Mode Detection Tool
            Created by: Youssef Lahouifi
            Supervised by : Redouan Korchiyne
            
[ Debug Mode Scanner - Test various methods to detect debug mode ]

[*] Starting scan at 2025-04-12 23:01:12
[*] Testing 1 target(s)

[+] Potential Debug Mode Detected on https://target.com
    -> Technique: HTTP Method POST
    -> Fingerprint: Symfony\Component\
    -> Technique: HTTP Method PUT
    -> Fingerprint: Symfony\Component\
    -> Technique: Malformed JSON ({"foo":"bar")
    -> Fingerprint: Symfony\Component\

[*] Scan Summary:
    -> Completed in: 7.35 seconds
    -> Targets scanned: 1
    -> Vulnerable targets: 1
    -> Success rate: 100.0%

```

## Limitation and things to improve

- Slow
- doesnt contain all patterns , it might miss vulnerabilities
- False positive in some cases

