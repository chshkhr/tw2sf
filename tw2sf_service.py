# http://www.chrisumbel.com/article/windows_services_in_python
import win32service
import win32serviceutil
import win32event


class PySvc(win32serviceutil.ServiceFramework):
    # you can NET START/STOP the service by the following name
    _svc_name_ = "TeamworkSvc"
    # this text shows up as the service name in the Service
    # Control Manager (SCM)
    _svc_display_name_ = "Teamwork-Shopify Service"
    # this text shows up as the description in the SCM
    _svc_description_ = "This service gets data from Teamwork API and sends them to Shopify API"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # create an event to listen for stop requests on
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    # core logic of the service
    def SvcDoRun(self):
        import sys
        import os
        import teamworker
        import shopifier
        import utils

        utils.mkdirs()
        fn = os.path.join(utils._DIR, 'log', utils.time_str() + '.log')
        f = open(fn, 'w')
        sys.stdout = f

        def log(s):
            f.write(f'{utils.time_str()}: {s}\n')
            f.flush()

        try:
            rc = None

            # if the stop event hasn't been fired keep looping
            while rc != win32event.WAIT_OBJECT_0:
                tw = None
                try:
                    log('Run Teamworker')
                    tw = teamworker.Teamwork2Shopify()
                    tw.init_tw()
                    tw.import_styles()
                    tw.import_rta_by_date()
                except Exception as e:
                    log(e)
                finally:
                    if tw and tw.db:
                        try:
                            tw.db.close()
                        except Exception:
                            pass

                try:
                    log('Run Shopifier')
                    shopifier.init_sf()
                    shopifier.export_styles()
                    shopifier.export_qty()
                except Exception as e:
                    log(e)
                finally:
                    try:
                        shopifier.db.close()
                    except Exception:
                        pass

                # block and listen for a stop event
                log('Sleep for 5 minutes\n')
                rc = win32event.WaitForSingleObject(self.hWaitStop, 300000)

        except Exception as e:
            log(e)
        finally:
            log('SHUTTING DOWN')
            sys.stdout = sys.__stdout__
            f.close()

    # called when we're being shut down
    def SvcStop(self):
        # tell the SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # fire the stop event
        win32event.SetEvent(self.hWaitStop)


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(PySvc)
