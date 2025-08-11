# Local Social Networking Protocol (LSNP)

### Installing Software Requirements
Before running the LSNP program, make sure your system has the required software installed.

Software Requirements
* Python (version 3.8 or above recommended)
* pip (Python package installer)

#### Windows
1. Check if Python is installed
Open Terminal and run:
    ```
    python --version
    ```
If you see a version number, Python is already installed.
If not, download Python and install it:
* https://www.python.org/downloads/windows/

2. Verify pip installation
    ```
    pip --version
    ```
If pip is not found, reinstall Python and ensure pip is included.

#### MAC
1. Check if Python is installed
Open Terminal and run:
    ```
    python3 --version
    ```
If not installed, install Python via Homebrew:
    ```
    brew install python
    ```
    
2. Verify pip installation
    ```
    pip3 --version
    ```
If not found, install pip with:
    ```
    python3 -m ensurepip --upgrade
    ```

### Running The Program
#### Windows
*  Non-verbose mode:
    ```
    python LSNP.py <Name>
    ```
*  Verbose mode:
    ```
    python LSNP.py <Name> --verbose
    ```

#### MAC
*  Non-verbose mode:
    ```
    python3 LSNP.py <Name>
    ```
*  Verbose mode:
    ```
    python3 LSNP.py <Name> --verbose
    ```
*  Replace <Name> with a unique name for each terminal (e.g., Alice, Bob, Charlie). This name will serve as the identifier for each peer in the local network.

### Work Distribution Matrix

| Task / Role | Filipino, Eunice Marble | Filipino, Audric Justin | Lazaro, Heisel Janine | Wee, Justine Erika |
| :--- | :---: | :---: | :---: | :---: |
| **Network Communication** | | | | |
| UDP Socket Setup | | Reviewer | Primary | Secondary |
| mDNS Discovery Integration | | Reviewer | Primary | Secondary |
| IP Address Logging | | Secondary | Primary | Reviewer |
| **Core Feature Implementation** | | | | |
| Core Messaging (POST, DM, LIKE, FOLLOW) | Primary | Reviewer | Secondary | |
| File Transfer (Offer, Chunk, ACK) | Reviewer | Primary | Reviewer | |
| Tic Tac Toe Game (with recovery) | Reviewer | Secondary | | Primary |
| Group Creation / Messaging | Primary | Reviewer | Primary | Secondary |
| Induced Packet Loss (Game & File) | | | Secondary | Reviewer |
| Acknowledgement / Retry | Secondary | Reviewer | Primary | |
| **UI & Logging** | | | | |
| Verbose Mode Support | Primary | | Secondary | Reviewer |
| Terminal Grid Display | Reviewer | | Secondary | Primary |
| Message Parsing & Debug Output | Secondary | Primary | | Reviewer |
| **Testing and Validation** | | | | |
| Inter-group Testing | Primary | Primary | | Secondary |
| Correct Parsing Validation | Primary | Reviewer | Secondary | |
| Token Expiry & IP Match | Secondary | | Primary | Reviewer |
| **Documentation & Coordination** | | | | |
| RFC & Project Report | | Reviewer | | Secondary |
| Milestone Tracking & Deliverables | Secondary | | Primary | Reviewer |

## Authors
* Filipino, Eunice Marble (eunice_filipino@dlsu.edu.ph)
* Filipino, Audric Justin (audric_filipino@dlsu.edu.ph)
* Lazaro, Heisel Janine (heisel_lazaro@dlsu.edu.ph)
* Wee, Justine Erika (justine_wee@dlsu.edu.ph)

## AI Use Declaration
During the preparation of this work the authors used ChatGPT, CoPilot and Gemini for the following purposes:
1. Generating portions of the source code 
2. Provide assistance in documentation
3. Provide coding assistance such as debugging errors in code
4. Understanding the syntax and protocol-related concepts
5. Providing commands for running the features of the program

After using these tools/services, the authors reviewed and edited the content as needed and take full responsibility for the content of the publication.

