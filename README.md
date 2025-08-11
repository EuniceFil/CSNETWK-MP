# Local Social Networking Protocol (LSNP)

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
*  <Name> will be the names for each of the three terminals

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
2. To refine and improve written content
3. Provide coding assistance such as debugging errors in code
4. Understanding the syntax and protocol-related concepts
5. Providing commands for running the features of the program

After using these tools/services, the authors reviewed and edited the content as needed and take full responsibility for the content of the publication.

