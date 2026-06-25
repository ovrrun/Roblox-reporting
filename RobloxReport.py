import requests
from datetime import datetime
import random
import argparse
import sys
from colorama import Fore, Style, init
init(autoreset=True)

DEBUG_LEVELS = {
    "quiet": 0,
    "info": 1,
    "debug": 2,
}
debugLevel = 1
reportTargetUserId = None

def LogMessage(message, messageType="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if messageType == "SUCCESS" and debugLevel >= 1:
        print(f"{Fore.GREEN}[{timestamp}] [SUCCESS] {message}{Style.RESET_ALL}")
    elif messageType == "ERROR" and debugLevel >= 1:
        print(f"{Fore.RED}[{timestamp}] [ERROR] {message}{Style.RESET_ALL}")
    elif messageType == "WARNING" and debugLevel >= 1:
        print(f"{Fore.YELLOW}[{timestamp}] [WARNING] {message}{Style.RESET_ALL}")
    elif messageType == "DEBUG" and debugLevel >= 2:
        print(f"{Fore.BLUE}[{timestamp}] [DEBUG] {message}{Style.RESET_ALL}")
    elif messageType == "INFO" and debugLevel >= 1:
        print(f"{Fore.CYAN}[{timestamp}] [INFO] {message}{Style.RESET_ALL}")

def PrintUsage():
    usage = f"""
{Fore.MAGENTA}=== Roblox Report Handler ==={Style.RESET_ALL}
{Fore.CYAN}Usage:{Style.RESET_ALL}
    {Fore.GREEN}py ReportHandler.py -u <username> [--debug|--quiet]{Style.RESET_ALL}
    {Fore.GREEN}py ReportHandler.py -i <userid>   [--debug|--quiet]{Style.RESET_ALL}
{Fore.CYAN}Options:{Style.RESET_ALL}
    {Fore.YELLOW}-u, --username   {Fore.CYAN}Username to report{Style.RESET_ALL}
    {Fore.YELLOW}-i, --userid     {Fore.CYAN}User ID to report{Style.RESET_ALL}
    {Fore.YELLOW}--debug          {Fore.CYAN}Enable debug logging{Style.RESET_ALL}
    {Fore.YELLOW}--quiet          {Fore.CYAN}Disable info logging (only errors and successes){Style.RESET_ALL}
{Fore.YELLOW}Example:{Style.RESET_ALL}
    {Fore.GREEN}py ReportHandler.py -u "SomeUser123" --debug{Style.RESET_ALL}
    {Fore.GREEN}py ReportHandler.py -i 123456789 --quiet{Style.RESET_ALL}
"""
    print(usage)

def ResolveUserId(username=None, userId=None):
    global reportTargetUserId
    if userId:
        reportTargetUserId = userId
        return
    if username:
        try:
            response = requests.post(
                "https://users.roblox.com/v1/usernames/users",
                headers={"Content-Type": "application/json"},
                json={"usernames": [username], "excludeBannedUsers": False}
            )
            if response.status_code == 200 and response.json()["data"]:
                reportTargetUserId = str(response.json()["data"][0]["id"])
                LogMessage(f"Resolved username '{username}' to user ID: {reportTargetUserId}", "INFO")
                return
            else:
                LogMessage(f"Failed to resolve username '{username}': {response.text}", "ERROR")
                exit(1)
        except Exception as e:
            LogMessage(f"Error resolving username: {e}", "ERROR")
            exit(1)
    else:
        print(f"{Fore.RED}Error: one of the arguments -u/--username or -i/--userid is required{Style.RESET_ALL}", file=sys.stderr)
        PrintUsage()
        exit(1)

def FormatProxy(proxyLine):
    try:
        host, port, user, password = proxyLine.split(':')
        return f"http://{user}:{password}@{host}:{port}"
    except Exception as e:
        LogMessage(f"Failed to parse proxy line: {proxyLine}. Error: {e}", "ERROR")
        return None

def IsCookieValid(session):
    try:
        response = session.get("https://www.roblox.com/home", timeout=10)
        if response.status_code != 200:
            LogMessage(f"Cookie validation failed: HTTP {response.status_code}", "WARNING")
            return False
        return True
    except requests.exceptions.SSLError as e:
        LogMessage(f"SSL/Proxy error validating cookie: {e}", "WARNING")
        return "proxy_error"
    except Exception as e:
        LogMessage(f"Network error validating cookie: {e}", "WARNING")
        return "network_error"

def GetUserId(session):
    try:
        response = session.get("https://users.roblox.com/v1/users/authenticated", timeout=10)
        if response.status_code == 200:
            return str(response.json().get("id", ""))
        else:
            LogMessage(f"Failed to fetch user ID: {response.text}", "ERROR")
            return None
    except Exception as e:
        LogMessage(f"Error fetching user ID: {e}", "ERROR")
        return None

def GetXsrfToken(session):
    LogMessage("Fetching XSRF token...", "DEBUG")
    try:
        response = session.post("https://auth.roblox.com/v2/logout", timeout=10)
        xsrfToken = response.headers.get("x-csrf-token")
        if not xsrfToken:
            LogMessage("Failed to fetch XSRF token!", "ERROR")
            return None
        LogMessage(f"XSRF token fetched: {xsrfToken}", "DEBUG")
        return xsrfToken
    except Exception as e:
        LogMessage(f"Error fetching XSRF token: {e}", "ERROR")
        return None

def SendReport(session, xsrfToken, submitterUserId):
    headers = {
        "authority": "apis.roblox.com",
        "method": "POST",
        "path": "/abuse-reporting/v2/abuse-report",
        "scheme": "https",
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "referer": "https://www.roblox.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "x-csrf-token": xsrfToken
    }
    body = {
        "tags": {
            "ENTRY_POINT": {"valueList": [{"data": "website"}]},
            "REPORTED_ABUSE_CATEGORY": {"valueList": [{"data": "account theft - phishing, hacking, trading"}]},
            "REPORTED_ABUSE_VECTOR": {"valueList": [{"data": "user_profile"}]},
            "REPORTER_COMMENT": {"valueList": [{"data": "One of my friends from our friend group had their account stolen. Someone accessed the account without permission and took control of it. Please disable the account if necessary and investigate this issue to prevent further damage. Thank you."}]},
            "SUBMITTER_USER_ID": {"valueList": [{"data": submitterUserId}]},
            "REPORT_TARGET_USER_ID": {"valueList": [{"data": reportTargetUserId}]}
        }
    }
    LogMessage("Sending POST request to Roblox API...", "DEBUG")
    try:
        response = session.post(
            "https://apis.roblox.com/abuse-reporting/v2/abuse-report",
            headers=headers,
            json=body,
            timeout=10
        )
        return response
    except Exception as e:
        LogMessage(f"Error sending report: {e}", "ERROR")
        return None

def ProcessCookie(cookie, proxies):
    random.shuffle(proxies)
    for proxyLine in proxies:
        proxyUrl = FormatProxy(proxyLine)
        if not proxyUrl:
            continue
        LogMessage(f"Using proxy: {proxyUrl}", "DEBUG")
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
        })
        session.proxies = {
            "http": proxyUrl,
            "https": proxyUrl
        }
        session.cookies.set(".ROBLOSECURITY", cookie)
        cookieValid = IsCookieValid(session)
        if cookieValid == "proxy_error" or cookieValid == "network_error":
            LogMessage("Proxy/network error. Trying next proxy...", "WARNING")
            continue
        if not cookieValid:
            LogMessage("Cookie is invalid or expired. Skipping...", "WARNING")
            return False
        submitterUserId = GetUserId(session)
        if not submitterUserId:
            LogMessage("Failed to fetch user ID. Trying next proxy...", "WARNING")
            continue
        LogMessage(f"Submitter User ID: {submitterUserId}", "DEBUG")
        xsrfToken = GetXsrfToken(session)
        if not xsrfToken:
            LogMessage("Failed to fetch XSRF token. Trying next proxy...", "WARNING")
            continue
        response = SendReport(session, xsrfToken, submitterUserId)
        if response:
            if response.status_code in (200, 201):
                reportId = response.json().get("reportId", "N/A")
                LogMessage(f"Report sent successfully! Report ID: {reportId}", "SUCCESS")
                return True
            else:
                LogMessage(f"Report failed with status {response.status_code}: {response.text}", "ERROR")
                continue
        else:
            LogMessage("Report failed (unknown error). Trying next proxy...", "ERROR")
            continue
    LogMessage("All proxies failed for this cookie.", "WARNING")
    return False

def Main():
    global debugLevel
    parser = argparse.ArgumentParser(
        description="Roblox Report Handler",
        add_help=False,
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--quiet", action="store_true", help="Disable info logging (only errors and successes)")
    parser.add_argument("-h", "--help", action="store_true", help="Show this help message and exit")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-u", "--username", help="Username to report")
    group.add_argument("-i", "--userid", help="User ID to report")
    try:
        args = parser.parse_args()
    except SystemExit:
        print(f"{Fore.RED}Error: one of the arguments -u/--username or -i/--userid is required{Style.RESET_ALL}", file=sys.stderr)
        PrintUsage()
        exit(1)
    if args.help:
        PrintUsage()
        exit(0)
    if args.debug:
        debugLevel = 2
    elif args.quiet:
        debugLevel = 0
    ResolveUserId(args.username, args.userid)
    try:
        with open("cookies.txt", "r") as f:
            cookies = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        LogMessage("cookies.txt not found!", "ERROR")
        return
    try:
        with open("proxies.txt", "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        LogMessage("proxies.txt not found!", "ERROR")
        return
    LogMessage(f"Found {len(cookies)} cookies in cookies.txt", "INFO")
    LogMessage(f"Found {len(proxies)} proxies in proxies.txt", "INFO")
    LogMessage(f"Reporting user ID: {reportTargetUserId}", "INFO")
    validCookies = 0
    for i, cookie in enumerate(cookies, 1):
        LogMessage(f"Processing cookie {i}/{len(cookies)}: {cookie[:20]}...", "INFO")
        success = False
        for _ in range(3):
            if ProcessCookie(cookie, proxies):
                validCookies += 1
                success = True
                break
            random.shuffle(proxies)
        if not success:
            LogMessage(f"Failed to send report for cookie {i} after multiple retries.", "ERROR")
    LogMessage(f"Done. {validCookies}/{len(cookies)} cookies were valid.", "INFO")

if __name__ == "__main__":
    Main()
